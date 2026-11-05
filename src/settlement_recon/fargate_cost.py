"""Estimate the Settlement Recon task's compute cost from the public AWS catalog."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.request import urlopen

REGION = "ap-south-1"
CATALOG_URL = (
    f"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/{REGION}/index.json"
)
MAX_CATALOG_BYTES = 4_000_000
CPU_UNITS = 256
MEMORY_MIB = 512
ARCHITECTURES = {"x86_64": "", "arm64": "ARM-"}


@dataclass(frozen=True)
class HourlyRates:
    vcpu_usd: Decimal
    gib_usd: Decimal


def monthly_compute(rates: HourlyRates, *, tasks: int, hours: Decimal) -> Decimal:
    if not 1 <= tasks <= 100 or not hours.is_finite() or not Decimal(0) < hours <= Decimal(744):
        raise ValueError("Use 1–100 tasks and more than zero through 744 hours")
    return (
        tasks
        * hours
        * (rates.vcpu_usd * Decimal(CPU_UNITS) / 1024 + rates.gib_usd * Decimal(MEMORY_MIB) / 1024)
    )


def _lookup(catalog: dict, usage: str) -> tuple[str, Decimal]:
    matching = [
        sku
        for sku, product in catalog["products"].items()
        if product["attributes"].get("usagetype") == usage
        and product["attributes"].get("regionCode") == REGION
    ]
    if len(matching) != 1:
        raise ValueError(f"Expected one AWS SKU for {usage}")
    sku = matching[0]
    dimensions = [
        dimension
        for term in catalog["terms"]["OnDemand"][sku].values()
        for dimension in term["priceDimensions"].values()
        if dimension["unit"] == "hours"
        and dimension["beginRange"] == "0"
        and dimension["endRange"] == "Inf"
    ]
    if len(dimensions) != 1:
        raise ValueError(f"Expected one on-demand hourly price for {sku}")
    price = Decimal(dimensions[0]["pricePerUnit"]["USD"])
    if not price.is_finite() or price <= 0:
        raise ValueError(f"Unexpected USD price for {sku}")
    return sku, price


def estimate(catalog_bytes: bytes, tasks: int, hours: Decimal) -> dict:
    catalog = json.loads(catalog_bytes)
    if catalog["offerCode"] != "AmazonECS":
        raise ValueError("Expected the AmazonECS price list")
    profiles = {}
    for name, modifier in ARCHITECTURES.items():
        prefix = f"APS3-Fargate-{modifier}"
        cpu_sku, cpu = _lookup(catalog, prefix + "vCPU-Hours:perCPU")
        ram_sku, ram = _lookup(catalog, prefix + "GB-Hours")
        amount = monthly_compute(HourlyRates(cpu, ram), tasks=tasks, hours=hours)
        profiles[name] = {
            "vcpus": {"sku": cpu_sku, "usd_per_vcpu_hour": str(cpu)},
            "memory": {"sku": ram_sku, "usd_per_gib_hour": str(ram)},
            "compute_usd": format(amount, "f"),
        }
    return {
        "catalog_url": CATALOG_URL,
        "catalog_version": catalog["version"],
        "publication_date": catalog["publicationDate"],
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "region": REGION,
        "task": {"cpu_units": CPU_UNITS, "memory_mib": MEMORY_MIB, "os": "Linux"},
        "tasks": tasks,
        "hours_per_task": str(hours),
        "profiles": profiles,
        "scope": "On-demand Fargate CPU and memory only. Excludes all other charges and credits.",
        "arm64_assumption": "Requires an ARM-compatible image and a separate performance check.",
    }


def _decimal_argument(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("Enter a decimal number") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--hours", type=_decimal_argument, default=Decimal(730))
    parser.add_argument("--architecture", choices=ARCHITECTURES, default="x86_64")
    parser.add_argument("--max-compute-usd", type=_decimal_argument)
    args = parser.parse_args()
    cap = args.max_compute_usd
    if cap is not None and (not cap.is_finite() or cap < 0):
        parser.error("Budget must be a finite nonnegative USD amount")

    try:
        # The HTTPS destination is a fixed AWS public catalog, with no credentials.
        with urlopen(CATALOG_URL, timeout=15) as response:  # nosec B310
            if response.geturl() != CATALOG_URL:
                raise ValueError("Unexpected catalog redirect")
            raw = response.read(MAX_CATALOG_BYTES + 1)
        if len(raw) > MAX_CATALOG_BYTES:
            raise ValueError("AWS catalog exceeded the download limit")
        report = estimate(raw, args.tasks, args.hours)
    except (KeyError, ValueError, InvalidOperation, URLError, TimeoutError) as error:
        parser.exit(2, f"Cost estimate unavailable: {error}\n")

    passed = cap is None or Decimal(report["profiles"][args.architecture]["compute_usd"]) <= cap
    report["budget"] = {
        "architecture": args.architecture,
        "max_compute_usd": str(cap) if cap is not None else None,
        "passed": passed,
    }
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

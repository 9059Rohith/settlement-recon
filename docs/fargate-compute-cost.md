# Settlement Recon Fargate compute check

This CLI reads the public Amazon ECS price catalog for the Mumbai region without AWS credentials. It selects the four Linux on-demand CPU and memory price dimensions by usage type, records their SKUs, and hashes the downloaded catalog. The task size matches the ECS Terraform definition. [AWS bulk price catalog](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api.html)

Run the command in the environment prepared by the README's local setup, including the editable project installation. [Local setup](../README.md#run-the-local-demonstration)

```bash
python -m settlement_recon.fargate_cost --tasks 1 --hours 730 --max-compute-usd 10
```

The command prints a JSON comparison and exits with status 1 if the selected architecture exceeds the compute cap. It exits with status 2 if the input is invalid or the catalog cannot be verified. The recorded catalog estimated **$9.466275** on x86 and **$5.301625** on ARM for one task over 730 hours. ARM is a candidate for a separate compatibility and load test. The estimate covers Fargate CPU and memory. RDS, load balancing, storage, VPC endpoints, network transfer, taxes, credits, and regional discounts are outside this calculation. The observed data comes from the published Amazon ECS catalog and is an estimate for the stated profile. [Recorded run](../evidence/fargate-compute-estimate.json) · [Fargate billing scope](https://aws.amazon.com/fargate/pricing/)

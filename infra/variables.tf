variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "name" {
  type    = string
  default = "settlement-recon"
}
variable "image" {
  type        = string
  description = "Immutable ECR image digest or unique commit tag. No latest tag."
  validation {
    condition     = !endswith(var.image, ":latest")
    error_message = "Use an immutable digest or commit tag."
  }
}
variable "api_secret_arn" {
  type        = string
  description = "Existing Secrets Manager secret whose plain value is a >=32 character API token."
}
variable "certificate_arn" {
  type        = string
  description = "Existing issued ACM certificate in this AWS region for the DNS name you will point at the ALB."
}
variable "desired_count" {
  type    = number
  default = 1
}

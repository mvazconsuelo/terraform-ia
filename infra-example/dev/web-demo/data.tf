# Data sources: what is read or built from other resources, not created
data "aws_iam_policy_document" "read_db_secret" {
  statement {
    sid       = "ReadDatabaseSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.database.master_user_secret_arn]
  }
}

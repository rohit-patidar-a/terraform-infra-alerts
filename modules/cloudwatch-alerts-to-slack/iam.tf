#####
# IAM roles
#

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "lambda_sns_to_slack" {
  name               = var.lambda_iam_role_name
  permissions_boundary = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/ccoe/js-developer"
  assume_role_policy = file("${path.module}/policies/lambda-assume-role.json")
}

#####
# IAM policies
#

resource "aws_iam_role_policy" "lambda_sns_to_slack" {
  name   = var.lambda_iam_policy_name
  role   = aws_iam_role.lambda_sns_to_slack.id
  policy = file("${path.module}/policies/lambda-role-policy.json")
}
# Security policy

## Reporting a vulnerability

Report it privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability** (private vulnerability reporting). Do not open a public issue or pull request for a vulnerability. Include the version or commit, the steps to reproduce and, for a parser problem, the smallest input that shows it. Do not attach a PDF you do not have the right to share.

## Supported versions

Only the default branch (`main`) is supported. There are no maintained release branches.

## Scope

The application is an offline tool that binds `127.0.0.1` only. Problems in how it reads untrusted PDF bytes, in its request guards, in how it stores notes, or in how document text reaches the page are in scope.

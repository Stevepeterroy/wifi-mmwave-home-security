# Security and local configuration

Never commit passwords, API tokens, device pairing keys, signing keys or private certificates. Use the provided templates and keep deployment values in ignored local configuration. Build artifacts and local runtime data can embed secrets and must stay out of public commits.

This repository was prepared as a fresh source snapshot without previous Git history. A clean scan cannot guarantee the absence of every possible secret. Rotate any credential previously shared or committed; removing it from a source snapshot does not revoke it.

For a security concern, avoid posting credentials in public issues. Contact the repository owner privately through a contact method they explicitly provide.

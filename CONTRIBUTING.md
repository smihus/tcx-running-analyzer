# Contributing

Thanks for your interest! Contributions and bug fixes are welcome.

- Open an issue describing expected behavior before major feature changes.
- Keep the runtime standard-library-only where practical; support Python 3.10+.
- Add or update synthetic fixture tests with every parser behavior change.
- Run `python -m unittest discover -s tests -v` before opening a pull request.
- Don't include real Garmin activities or personal training metrics in tests, docs or issues.
- Preserve old JSON fields and document schema changes. New optional fields are preferable to renaming existing ones.
- Note that Windows PowerShell 5.1 must remain supported.

By contributing, you agree that your contribution is licensed under this repository's MIT license.

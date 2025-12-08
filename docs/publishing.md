# Publishing to PyPI

This guide outlines the steps to register on PyPI and publish `figquilt` using `uv`.

## 1. Registration

### Create Accounts
1.  **TestPyPI** (Recommended for testing):
    - Go to [test.pypi.org](https://test.pypi.org/account/register/).
    - Create an account.
    - Enable 2FA (Two-Factor Authentication) in Account Settings; this is **required** to publish.
2.  **PyPI** (For production):
    - Go to [pypi.org](https://pypi.org/account/register/).
    - Create an account.
    - Enable 2FA.

### generate API Tokens
For both environments, you need to generate an API token to authenticate uploads.
1.  Go to **Account Settings** > **API Tokens**.
2.  Click **Add API Token**.
3.  Scope: Select "Entire account" (since you haven't created the project yet).
4.  Copy the token (starts with `pypi-`). **Save this securely**; you won't see it again.

## 2. Project Metadata Preparation

Before publishing, ensure `pyproject.toml` has all necessary metadata:
- [ ] **Description**: Ensure it's accurate (already done).
- [ ] **License**: Add `license = { file = "LICENSE" }` or `text = "MIT"`.
- [ ] **Classifiers**: Add identifying tags (e.g., OS, License, Python version).
  ```toml
  classifiers = [
      "Programming Language :: Python :: 3",
      "License :: OSI Approved :: MIT License",
      "Operating System :: OS Independent",
  ]
  ```
- [ ] **URLs**: Add links to the repo.
  ```toml
  [project.urls]
  Homepage = "https://github.com/yourusername/figquilt"
  Repository = "https://github.com/yourusername/figquilt"
  ```

## 3. Build & Publish Workflow

### Build
Create the distribution files (`.tar.gz` and `.whl`):
```bash
uv build
```
This creates a `dist/` directory.

### Publish

**To TestPyPI:**
```bash
uv publish --publish-url https://test.pypi.org/legacy/ --token <YOUR_TESTPYPI_TOKEN>
```

**To PyPI (Production):**
```bash
uv publish --token <YOUR_PYPI_TOKEN>
```

> **Tip**: You can assume the token via environment variable `UV_PUBLISH_TOKEN` to avoid pasting it in the command line.

## 4. Verification
- Visit your project page on PyPI (e.g., `pypi.org/project/figquilt`).
- Try installing it in a fresh environment:
  ```bash
  uv pip install figquilt
  ```

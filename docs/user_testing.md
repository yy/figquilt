# Testing as an End User

To ensure `figquilt` works correctly for users, you should test the installation and usage in a clean environment, simulating how a real user would interact with the package.

## 1. Local Build Verification (Fastest)
Simulate a user installing the wheel file directly.

1.  **Build the package**:
    ```bash
    uv build
    ```
    This creates `.whl` and `.tar.gz` files in `dist/`.

2.  **Create a fresh environment**:
    Move to a temporary directory to ensure you aren't importing the local source code by mistake.
    ```bash
    cd /tmp
    mkdir figquilt-test
    cd figquilt-test
    uv venv
    source .venv/bin/activate
    ```

3.  **Install from wheel**:
    Replace `x.y.z` with the version built.
    ```bash
    # Path to your project dist folder
    uv pip install /path/to/your/git/figquilt/dist/figquilt-0.1.0-py3-none-any.whl
    ```

4.  **Verify**:
    ```bash
    figquilt --help
    ```

## 2. TestPyPI Verification (Closest to Production)
Test the full upload and download cycle without affecting the real PyPI.

1.  **Publish to TestPyPI** (see `publishing.md`).

2.  **Install from TestPyPI**:
    TestPyPI often misses some dependencies (like `pymupdf`), so you might need to point to the real PyPI for dependencies while fetching `figquilt` from TestPyPI.
    ```bash
    uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ figquilt
    ```

3.  **Verify**:
    ```bash
    figquilt --version
    ```

## 3. "Eat Your Own Dogfood"
Use `figquilt` in a real project of yours.

1.  Create a separate project folder (e.g., `my-paper-figures`).
2.  Install `figquilt` (via local editable install or wheel).
3.  Try to compose a complex figure for a real paper or presentation.
4.  Note down any friction points or confusing error messages.

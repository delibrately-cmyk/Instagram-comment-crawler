# Instagram Comment Crawler (Single Post)

[English README](README.md) | [中文说明](README_CN.md)

Fetch comments and replies from one public Instagram post using a logged-in browser session captured via Playwright.

## What This Tool Can Do

Below is what you can do with this program:

- Collect comments and replies from a public Instagram post.
- Capture required auth headers/cookies and endpoint metadata without using the official Instagram API.
- Support resume mode for interrupted crawling tasks.

## Important Notes

- This crawler can fail when Instagram updates its web endpoints or anti-bot rules.
- If you encounter issues, re-capture auth/endpoints first, then review the troubleshooting section.

## What You Need

- Python 3.10+ (recommended: 3.11/3.12)
- Windows PowerShell (examples below use Windows commands)
- A valid Instagram account that can open the target post

## Step-by-Step Setup and Run

### Step 1. Enter Project Directory

```powershell
cd .\ig-comment-crawler
```

Expected result: you can see `ig_crawler.py`, `run_ig_crawler.py`, and `config.example.json` in this folder.

### Step 2. Create and Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```
Expected result: terminal prefix shows `(.venv)`.

### Step 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
```
Expected result: install completes without error.

### Step 4. Create Local Config Files

```powershell
copy config.example.json config.json
copy .env.example .env
```
Expected result: `config.json` and `.env` are created in root directory.
Important: `config.json` and `.env` are sensitive local files. Do not commit them.

### Step 5. Capture Auth and Endpoints

```powershell
python ig_auth_setup.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/"
```

In the opened browser:

- Log in to Instagram
- If login shows password error and asks for secondary verification, complete the verification first. Then copy the one-time login link from your email and open that link inside the Playwright browser started by Python.
- Open your target post URL
- Scroll comments to trigger comment-related network requests
- Wait a few seconds
- Return to terminal and press `Ctrl+C` to finish capture

Expected result:

- `config.json` gets cookies/headers/endpoints
- `.env` gets cookie/header env vars
- capture log is saved under `crawler_data/raw_responses/`

### Step 6. Verify Config Before Crawling

Open `config.json` and check these are not `YOUR_...` placeholders:

- `instagram.authentication.cookies`
- `instagram.authentication.headers`
- `instagram.endpoints.comments`
- `instagram.endpoints.comment_replies`

Optional but recommended:

- `instagram.endpoints.post_by_shortcode`

### Step 7. Run the Crawler

```powershell
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/"
```

Expected result:

- Terminal prints `Saved: ...`
- Terminal prints `Comments: ...`
- output JSON is saved to `crawler_data/ig_comments/`

### Step 8. Optional Runtime Flags

```powershell
# Stop after N unique comments (includes replies)
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --max-comments 400

# Resume from previous state
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --resume

# Force no resume for this run
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --no-resume

# Disable replies
python run_ig_crawler.py --post-url "https://www.instagram.com/p/POST_SHORTCODE/" --no-replies
```

Resume state path:

- `crawler_data/ig_comments/<shortcode>_resume.json`

### Step 9. Run Tests

```powershell
python -m pytest -q
```

Expected result: all tests pass.

## Config Details

`config.json` endpoint structure:

- `type`: `graphql` or `rest`
- `method`: `POST` or `GET`
- `url`: endpoint URL
- `doc_id` or `query_hash` for GraphQL
- `variables`: supports placeholders `{shortcode}`, `{cursor}`, `{comment_id}`, `{media_id}`

Example:

```json
{
  "shortcode": "{shortcode}",
  "first": 50,
  "after": "{cursor}"
}
```

## Output Structure

Main output JSON includes:

- `post`: `url`, `shortcode`, `media_id`, `owner_id`, `caption`
- `comments`: top-level comments with nested `replies`
- `comment_count`, `expected_comment_count`, `fetched_at`, `pages`

### Example Output

```json
{
  "post": {
    "media_id": "3822619...",
    "url": "https://www.instagram.com/p/POST_SHORTCODE/",
    "shortcode": "POST_SHORTCODE"
  },
  "comment_count": 3927,
  "comments": [
    {
      "id": "1825540...",
      "text": "🔥🔥🔥🔥",
      "created_at": "2026-02-01T02:26:48Z",
      "like_count": 130,
      "user": {
        "id": "46481...",
        "username": "example_user",
        "is_verified": true
      },
      "replies": []
    }
  ]
}
```

## Performance Tuning

Tune these keys in `config.json`:

```text
instagram.settings.requests_per_minute
instagram.settings.comments_first
instagram.settings.replies_first
instagram.settings.fetch_replies
instagram.settings.request_jitter_ratio
instagram.settings.resume_by_default
instagram.settings.save_raw_responses
instagram.settings.raw_responses_keep
instagram.settings.raw_responses_max_mb
```

## Troubleshooting

- `403`/`429`: lower `requests_per_minute`, then re-capture auth.
- Missing comments/replies: recapture endpoint requests and update `doc_id`/variables.
- `ModuleNotFoundError` when running tests: run from project root with `python -m pytest -q`.

## Legal and Responsible Use

- Use only where you are authorized.
- Comply with Instagram terms and local laws.
- Do not collect personal data without legal basis.
- Do not use this project to bypass platform protections.

## Known Limitations

- Instagram `doc_id` and request schema can change at any time.
- Auth cookies/tokens expire and need refresh.
- Anti-abuse/rate limits may block requests (`403`, `429`).
- Local tests validate parser/state/CLI logic, not live API stability.

## License

MIT. See `LICENSE`.

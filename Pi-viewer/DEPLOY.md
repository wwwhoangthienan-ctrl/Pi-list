# Deploying to Render (free tier)

## Files in this folder
- `search_server.py` — the app
- `build_kmer_index.py` — offline indexer (run once, before deploying)
- `requirements.txt` — flask + gunicorn
- `pi_digits_2M.txt` — a ready-made 2,000,000-digit starter file (~2MB)
- `pi_digits_2M.txt.k6.index.json` — its prebuilt k=6 index (~27MB)

Both files are small enough to commit straight into a GitHub repo (GitHub's
hard limit is 100MB per file — no Git LFS needed at this size). This lets
you test the full pipeline live before worrying about a real billion-digit
file, which WILL need a different storage approach (see the NOTES section
in `build_kmer_index.py`).

## Steps

1. **Push this folder to a GitHub repo.**

2. **On render.com:** New → Web Service → connect the repo.

3. **Configure the service:**
   - Root Directory: `server/own_index` (wherever this folder lives in your repo)
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -b 0.0.0.0:$PORT search_server:app`
   - Instance Type: Free

4. **Set environment variables** (Render dashboard → your service → Environment):
   - `DIGIT_FILE` = `pi_digits_2M.txt`
   - `INDEX_K` = `6`

5. **Deploy.** Render gives you a URL like `https://pi-search-xyz.onrender.com`.

6. **Test it's alive:**
   ```
   curl https://pi-search-xyz.onrender.com/digits?start=0&count=10
   ```
   should return `{"content":"3141592653","start":0}`

7. **Paste that URL into `DigitService.lua`'s `BASE_URL`** back in your Roblox project.

## Free tier behavior
Spins down after ~15 min idle, cold-starts (few seconds) on the next request.
Fine for testing/dev; if that lag is a problem once players are actually on,
Render's paid tier ($7/mo-ish) keeps it always warm.

## Swapping in a bigger digit file later
Same steps — just run `build_kmer_index.py` against your bigger file, commit
both files (or, past ~100MB, switch to Git LFS or an external storage bucket
and download it during the build step instead of committing it), and update
`DIGIT_FILE` to the new filename.

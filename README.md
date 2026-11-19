# halachabench.ai

Source of the public HalachaBench website, served by GitHub Pages from `docs/` behind Cloudflare.

Everything on the site comes from public material only:

- `../halacha-bench-results` (public repo): leaderboard table, notes, changelog, proof-bundle hashes, results chart
- `../hashkafa-bench-results` (public repo): stringency table, per-category CSV, charts
- `content/`: findings pages (Markdown), `values.json` (figures already posted on X), images already posted on X

## Update the site

1. Update and push the results repo(s) first. The site only shows what is already public there.
2. To add a finding, add `content/findings/YYYY-MM-DD-slug.md` with front matter
   (`title`, `date`, `study` = HalachaBench | HashkafaBench | Values, `summary`, optional `x`, `image`, `data`).
3. Build and check:

   ```
   python tools/build.py
   python tools/check_public.py
   ```

4. Preview: `python -m http.server 8787 --directory docs`, open http://localhost:8787.
5. Commit and push. GitHub Pages republishes `docs/` within a minute or two.

`build.py` stops if the README leaderboard and `bundle/scores.json` disagree, so a stale table cannot be published.
`check_public.py` fails on broken internal links, denied terms and long Hebrew passages outside the Hebrew page.

Analytics: Cloudflare Web Analytics. If the site is proxied by Cloudflare, enable it in the dashboard (no code needed);
otherwise put the beacon token in `content/site.json` as `cf_beacon_token` and rebuild.

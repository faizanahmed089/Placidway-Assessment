# Deploying to Hugging Face Spaces

The code is already committed in a local git repository on the `main` branch.
Deploying means pushing that repository to a Space. Steps 1-3 happen on the
Hugging Face website; step 4 is two commands.

## 1. Create the Space

1. Sign in at https://huggingface.co (create a free account if needed).
2. Open https://huggingface.co/new-space
3. Fill in:
   - **Space name:** for example `placidway-chatbot`
   - **SDK:** Docker, template **Blank**
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public
4. Click **Create Space**.

## 2. Add the secrets

In the Space: **Settings** -> **Variables and secrets** -> **New secret**. Add two:

| Name | Value |
|---|---|
| `GROQ_API_KEY` | the same key that is in your local `.env` |
| `ADMIN_TOKEN` | the `ADMIN_TOKEN` value from your local `.env` (or any long random string) |

Add them as **secrets**, not variables, so they are never shown publicly.

## 3. Create an access token for pushing

1. Open https://huggingface.co/settings/tokens
2. **Create new token**, type **Write**, any name.
3. Copy the token. You will paste it once as the password in step 4.

## 4. Push the code

Replace `YOUR_USERNAME` and `YOUR_SPACE_NAME`:

```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
```

```bash
git push --force space main
```

When asked to sign in: username = your Hugging Face username, password = the
token from step 3. `--force` is needed only this first time, because the new
Space already contains a starter commit that this push replaces.

## 5. Check it

1. Open the Space page and watch the **Logs** tab. The first build takes a few
   minutes. Wait for "Knowledge base ready: 107 chunks".
2. Your public URL is `https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space`
   (also under the Space's menu: **Embed this Space** -> Direct URL).
3. Open that URL in a private window and ask a question.
4. Ask the test questions from `test_results.md` and compare the answers.

Use the direct `.hf.space` URL in the Google form, not the
`huggingface.co/spaces/...` page.

## Updating later

After changing code:

```bash
git add -A
```

```bash
git commit -m "Describe the change"
```

```bash
git push space main
```

The Space rebuilds automatically.

## Keeping it up for 7 days

A free Space goes to sleep after about 48 hours without visitors and takes a
minute or so to wake on the next visit. Open the URL once a day during the
review week so reviewers do not hit a sleeping Space.

## If the build fails

Copy the error from the **Logs** tab. The Docker build has not been run on
this machine (Docker is not installed here), so the first build on Hugging
Face is its first real test.

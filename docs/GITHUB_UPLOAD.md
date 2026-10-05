# Publish LedgerLens on GitHub

## Repository details

- Name: `centralign-ledgerlens`
- Description: `A bounded autonomous financial research worker with data validation, human approvals, SQLite persistence and verified outcomes.`
- Visibility: Public if you want reviewers to open it without an invitation.
- Topics: `python`, `sqlite`, `workflow-automation`, `data-quality`, `financial-analysis`, `human-in-the-loop`.
- Website: leave blank until you have a publicly accessible demo. Localhost is not a public website.

The README includes actual screenshots, a demo link, architecture diagram, setup commands, test evidence, limitations and AI assistance disclosure. Do not add a passing CI badge until the uploaded workflow actually passes.

## Upload using the GitHub website

1. Extract `LedgerLens_GitHub_Ready.zip` into a new folder. This curated repository copy excludes local databases, browser caches and personal application/interview preparation documents.
2. Sign in at https://github.com and open https://github.com/new.
3. Enter the name and description above. Choose visibility. Leave automatic README, gitignore and license initialization off: the project provides its own README and gitignore. A license is your separate choice.
4. Click **Create repository**.
5. On the empty repository page, choose **uploading an existing file**. If files already exist, use **Add file > Upload files**.
6. Open the extracted `centralign-ledgerlens` folder. Drag its contents into the upload area, including subfolders. Do not upload just the ZIP or an extra enclosing folder. `README.md`, `worker.py` and `server.py` must be at the repository root.
7. Include `.github` and `.gitignore`. If the file picker hides them, enable hidden files or use Git below. The website does not apply `.gitignore` to manually uploaded files; use the curated ZIP rather than dragging the working directory.
8. Use commit message `Add LedgerLens financial research worker` and commit the changes.
9. Check the README images, diagram and demo link. Open **Actions** and inspect the Tests workflow. Its status is only known after GitHub runs it.

The package has fewer than 100 files, all below GitHub's 25 MiB browser-upload limit per file. Relative links allow the README to work without knowing your GitHub username.

## Git command-line alternative

Create the empty GitHub repository first. In PowerShell, navigate to the extracted project directory and run these commands individually:

```powershell
git init -b main
git add .
git status
git commit -m "Add LedgerLens financial research worker"
git remote add origin https://github.com/YOUR_USERNAME/centralign-ledgerlens.git
git push -u origin main
```

Replace `YOUR_USERNAME` before running the remote command. If Git requests an author identity, configure your actual name and GitHub-associated or GitHub-provided no-reply email, then retry the commit. Complete GitHub's sign-in flow when prompted. Do not store credentials in project files.

## Finishing touches

1. Set the description and topics in the repository's **About** panel.
2. Pin the repository on your GitHub profile if you want it featured.
3. Upload `artifacts/demo.webm` to Google Drive or another video host, enable reviewer access, and use that URL for the application video field. The repository copy remains a downloadable backup.
4. Replace the README demo link with the real shared video URL if you prefer external playback.
5. Open the repository and video while signed out to verify reviewer access.

The polished presentation does not change the scope: three fictional companies, no live arbitrary-company lookup, and no LLM call in the default demo.

References: [GitHub upload instructions](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository), [README relative links](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes), [Adding local code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

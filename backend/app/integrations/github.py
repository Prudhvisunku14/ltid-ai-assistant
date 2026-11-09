"""GitHub publication is intentionally NOT automated here without credentials.
Publishing steps (run by a human or the agent with a valid token):
  git remote add origin https://github.com/LTID-rep/ltid-ai-competition-website.git
  git push -u origin feature/northstar-homepage-upgrade
  gh pr create --draft --base main --head feature/northstar-homepage-upgrade
Never merge or deploy automatically."""

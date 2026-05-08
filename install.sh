git reset --soft HEAD~1
echo gittoken >> .gitignore
git rm --cached -f gittoken
git commit -m "Initial commit (remove secret)"
git push -u origin main

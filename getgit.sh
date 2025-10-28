# 1) Identify yourself (change the email!)
git config --global user.name "Daniel Hudsky"
git config --global user.email "hudsky@gmail.com"

# 2) Ensure we're on 'main'
git checkout -B main

# 3) Make an initial commit (pick ONE of the two options)

# Option A: You already have files to commit
git add .
git commit -m "Initial commit"

# Option B: Repo is empty — create a README and commit
# echo "# photon" > README.md
# git add README.md
# git commit -m "Initial commit"

# 4) Push to GitHub
git push -u origin main


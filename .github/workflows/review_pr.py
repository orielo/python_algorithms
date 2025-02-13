import os
import openai
import requests
import json
from github import Github

def get_pull_request_diff(repo_name, pr_number, token):
    print(f"Fetching PR diff for repo: {repo_name}, PR number: {pr_number}")
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/files"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    print(f"GitHub API response status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response content: {response.text}")
    return response.json() if response.status_code == 200 else None

def review_code_with_gpt(file_diffs):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    print("Sending code diff to OpenAI for review...")

    reviews = []
    general_summary = ""
    for file in file_diffs:
        file_name = file.get("filename")
        patch = file.get("patch", "")
        if not patch:
            continue

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You support software developers by providing detailed information about their pull request diff content from repositories hosted on GitHub. You help them understand the quality, security, and completeness implications of the pull request by providing concise feedback about the code changes based on known best practices."},
                {"role": "user", "content": f"Here is a code diff for file `{file_name}`:\n\n{patch}\n\nProvide a concise review with short, impactful, and straight-to-the-point inline comments. Additionally, generate a high-level summary of the overall changes in a separate response."}
            ]
        )
        review_text = response.choices[0].message.content
        split_reviews = review_text.split("Summary:")
        inline_comments = split_reviews[0].strip()
        general_summary += f"\n- {file_name}: {split_reviews[1].strip()}" if len(split_reviews) > 1 else ""
        reviews.append((file_name, patch, inline_comments))
    
    return reviews, general_summary

def post_inline_comments(repo_name, pr_number, token, reviews):
    print(f"Posting inline comments to PR #{pr_number} in repo {repo_name}")
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    pr_info_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    pr_info = requests.get(pr_info_url, headers=headers).json()
    commit_id = pr_info.get("head", {}).get("sha", "")
    if not commit_id:
        print("❌ Failed to get commit SHA")
        return
    
    for file_name, patch, review_text in reviews:
        lines = patch.split('\n')
        line_number = None
        position = 1

        for line in lines:
            if line.startswith('@@'):
                try:
                    line_number = int(line.split('+')[1].split(',')[0])
                    position = 1
                except:
                    continue
            elif line.startswith('+') and line_number:
                comment = {
                    "body": f"{review_text}",
                    "commit_id": commit_id,
                    "path": file_name,
                    "position": position
                }
                response = requests.post(url, headers=headers, json=comment)
                print(f"📌 Comment post status for {file_name}, position {position}: {response.status_code}, Response: {response.text}")
                position += 1

def post_general_summary(repo_name, pr_number, token, general_summary):
    print(f"Posting general summary to PR #{pr_number}")
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"body": f"### AI Code Review Summary:\n{general_summary}"}
    response = requests.post(url, headers=headers, json=data)
    print(f"General summary post status: {response.status_code}")

def main():
    repo_name = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")

    event_path = os.getenv("GITHUB_EVENT_PATH")
    print(f"Event path: {event_path}")
    pr_number = None

    if event_path and os.path.isfile(event_path):
        with open(event_path, 'r') as f:
            event_data = json.load(f)
            pr_number = event_data.get("pull_request", {}).get("number")
        print(f"Extracted PR number from event: {pr_number}")
    else:
        print("GITHUB_EVENT_PATH is missing or invalid.")

    if repo_name and pr_number and token:
        file_diffs = get_pull_request_diff(repo_name, pr_number, token)
        if file_diffs:
            print("Successfully fetched PR file diffs.")
            reviews, general_summary = review_code_with_gpt(file_diffs)
            post_inline_comments(repo_name, pr_number, token, reviews)
            post_general_summary(repo_name, pr_number, token, general_summary)
        else:
            print("Failed to fetch PR diff.")
    else:
        print(f"Missing environment variables. Repo: {repo_name}, PR number: {pr_number}, Token present: {bool(token)}")

if __name__ == "__main__":
    main()

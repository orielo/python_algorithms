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
    general_summary = []
    for file in file_diffs:
        file_name = file.get("filename")
        patch = file.get("patch", "")
        if not patch:
            continue

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert code reviewer. Your feedback should be precise, relevant, and actionable. Provide in-line comments that directly reference the specific code line. Additionally, generate a structured high-level summary that highlights key improvements, potential issues, and best practices."},
                {"role": "user", "content": f"Here is a code diff for file `{file_name}`:\n\n{patch}\n\nProvide short, impactful, and clear inline comments for each issue, ensuring they are directly tied to the correct lines. Do not generate empty or redundant comments. Also, generate a structured general summary with bullet points covering key improvements, potential problems, and best practices."}
            ]
        )
        review_text = response.choices[0].message.content.strip()
        
        if "Summary:" in review_text:
            inline_comments, summary = review_text.split("Summary:", 1)
        else:
            inline_comments, summary = review_text, "No general summary provided."
        
        general_summary.append(f"- **{file_name}**: {summary.strip()}" if summary.strip() else "- **{file_name}**: No general summary provided.")
        unique_comments = [c.strip() for c in set(inline_comments.split("\n")) if c.strip()]
        reviews.append((file_name, patch, unique_comments))
    
    return reviews, "\n".join(general_summary)

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
    
    for file_name, patch, inline_comments in reviews:
        lines = patch.split('\n')
        position = 1
        for line, comment in zip(lines, inline_comments):
            if line.startswith('+') and comment.strip():
                comment_data = {
                    "body": f"💡 *Suggested Improvement:* {comment}",
                    "commit_id": commit_id,
                    "path": file_name,
                    "position": position
                }
                response = requests.post(url, headers=headers, json=comment_data)
                print(f"📌 Comment post status for {file_name}, position {position}: {response.status_code}, Response: {response.text}")
            position += 1

def post_general_summary(repo_name, pr_number, token, general_summary):
    print(f"Posting general summary to PR #{pr_number}")
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    summary_text = general_summary.strip() if general_summary.strip() else "No general summary provided."
    data = {"body": f"## 🔍 AI Code Review Summary\n{summary_text}"}
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

import os
import openai
import requests
import json
from github import Github

def get_pull_request_diff(repo_name, pr_number, token):
    print(f"Fetching PR diff for repo: {repo_name}, PR number: {pr_number}")
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    print(f"GitHub API response status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response content: {response.text}")
    return response.text if response.status_code == 200 else None

def review_code_with_gpt(diff):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    print("Sending code diff to OpenAI for review...")

    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer. Provide constructive feedback on the following code changes."},
            {"role": "user", "content": diff}
        ]
    )
    return response.choices[0].message.content

def post_comment(repo_name, pr_number, token, comment):
    print(f"Posting comment to PR #{pr_number} in repo {repo_name}")
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"body": comment}
    response = requests.post(url, headers=headers, json=data)
    print(f"Comment post status: {response.status_code}")

def main():
    repo_name = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")

    # Fetch PR number from GitHub event payload
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
        diff = get_pull_request_diff(repo_name, pr_number, token)
        if diff:
            print("Successfully fetched PR diff.")
            review = review_code_with_gpt(diff)
            post_comment(repo_name, pr_number, token, review)
        else:
            print("Failed to fetch PR diff.")
    else:
        print(f"Missing environment variables. Repo: {repo_name}, PR number: {pr_number}, Token present: {bool(token)}")

if __name__ == "__main__":
    main()

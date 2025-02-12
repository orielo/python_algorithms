import os
import openai
import requests
from github import Github

def get_pull_request_diff(repo_name, pr_number, token):
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"}
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else None

def review_code_with_gpt(diff):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer. Provide constructive feedback on the following code changes."},
            {"role": "user", "content": diff}
        ]
    )
    return response["choices"][0]["message"]["content"]

def post_comment(repo_name, pr_number, token, comment):
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"body": comment}
    requests.post(url, headers=headers, json=data)

def main():
    repo_name = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("GITHUB_EVENT_PULL_REQUEST_NUMBER")
    token = os.getenv("GITHUB_TOKEN")
    
    diff = get_pull_request_diff(repo_name, pr_number, token)
    if diff:
        review = review_code_with_gpt(diff)
        post_comment(repo_name, pr_number, token, review)
    else:
        print("Failed to fetch PR diff.")

if __name__ == "__main__":
    main()
    
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx",
#   "pandas",
#   "seaborn",
#   "matplotlib",
#   "openai",
#   "tenacity",
#   "chardet",
# ]
# ///
import chardet
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_fixed

# Initialize OpenAI client with environment variable
client = OpenAI(base_url="https://aiproxy.sanand.workers.dev/openai/v1")

# Retry logic for API calls
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def call_openai(prompt, model="gpt-4o-mini", temperature=0.7):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        return None

def analyze_csv(file_path):
    try:
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
            encoding = result['encoding']
    except Exception as e:
        print(f"Error detecting encoding: {e}")
        encoding = 'utf-8'  # Default to utf-8 if detection fails

    # Try reading the file with detected encoding, handle encoding errors
    try:
        df = pd.read_csv(file_path, encoding=encoding)
    except UnicodeDecodeError as e:
        # Handle cases where chardet fails to detect the encoding or the file contains problematic characters
        print(f"Unicode decode error with encoding {encoding}: {e}")
        # Fallback to alternative encodings
        for fallback_encoding in ['ISO-8859-1', 'utf-16', 'utf-32']:
            try:
                df = pd.read_csv(file_path, encoding=fallback_encoding)
                print(f"Successfully read file with encoding: {fallback_encoding}")
                break
            except UnicodeDecodeError:
                continue
        else:
            print("All encoding attempts failed. Please check the file encoding manually.")
    summary = df.describe(include="all").transpose().to_string()
    null_counts = df.isnull().sum().to_string()
    column_info = {col: {"type": str(df[col].dtype), "sample_values": df[col].dropna().unique()[:5].tolist()} for col in df.columns}
    return df, summary, null_counts, column_info

def generate_visualizations(df, file_prefix):
    heatmap_path = None
    if df.select_dtypes(include=["number"]).shape[1] > 1:  # Ensure multiple numeric columns
        corr = df.select_dtypes(include=['number']).corr()
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr, annot=True, cmap="coolwarm")
        plt.title("Correlation Matrix")
        heatmap_path = f"{file_prefix}_correlation.png"
        plt.savefig(heatmap_path)
        plt.close()

    dist_plots = []
    for col in df.select_dtypes(include=["number"]).columns:
        plt.figure()
        sns.histplot(df[col], kde=True)
        plt.title(f"Distribution of {col}")
        plot_path = f"{file_prefix}_{col}_distribution.png"
        plt.savefig(plot_path)
        dist_plots.append(plot_path)
        plt.close()

    return {"heatmap": heatmap_path, "dist_plots": dist_plots}

def narrate_story(summary, null_counts, column_info, visualizations):
    prompt = (
        f"I have performed an analysis on a dataset. "
        f"Here is the summary:\n{summary}\n\n"
        f"Missing values count:\n{null_counts}\n\n"
        f"Column details:\n{column_info}\n\n"
        f"The visualizations created include a correlation matrix and distribution plots. "
        f"Please narrate a story about the dataset, analysis, insights, and implications."
    )

    response_content = call_openai(prompt)
    if not response_content:
        return "The AI could not generate a response due to an error."
    return response_content

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    file_path = sys.argv[1]
    file_prefix = file_path.split(".")[0]

    df, summary, null_counts, column_info = analyze_csv(file_path)
    visualizations = generate_visualizations(df, file_prefix)
    story = narrate_story(summary, null_counts, column_info, visualizations)

    with open(f"README.md", "w") as f:
        f.write("# Analysis Results\n\n")
        f.write(story)
        for viz_type, paths in visualizations.items():
            if isinstance(paths, list):
                for path in paths:
                    f.write(f"![{viz_type}]({path})\n")
            elif paths:
                f.write(f"![{viz_type}]({paths})\n")

if __name__ == "__main__":
    main()

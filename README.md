# DEEEP_GOV

DEEEP_GOV is a tool that evaluates Celo ecosystem projects and allocates votes between them based on configurable model personalities.

## Overview

The system works as follows:

1. You provide URLs for a Celo ecosystem project to evaluate
2. You select a personality model (eco_champion, tech_innovator, or community_builder)
3. The system analyzes the project according to the personality's priorities and criteria
4. It allocates votes between the projects proportionally to their evaluation scores
5. Results are output in JSON format with detailed reasoning

## Files

The system consists of these core files:

- `main.py`: The main script that handles browser interaction, project analysis, and workflow
- `model_specs.py`: Defines the model personalities with goals, priorities, and output formats
- `.env`: Contains your API key (you need to create this)

## Setup

1. Clone this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Anthropic API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

## Usage

Run the script with a project URL as an argument:

```bash
python main.py "https://easyretropgf.xyz/celorpgf0/projects/project1"
```

### Optional Arguments

- `--personality` or `-p`: Personality to use (eco_champion, tech_innovator, community_builder) [default: eco_champion]
- `--votes` or `-v`: Total number of votes to allocate [default: 100]
- `--output` or `-o`: Output file for results [default: evaluation_results.json]
- `--model` or `-m`: Anthropic model to use [default: claude-3-5-sonnet-20240620]

Example with all options:

```bash
python main.py "https://easyretropgf.xyz/celorpgf0/projects/0xfa196db3de60943d369f69466db14da0c4c930ba186d923a655fbf283d65c61e" --personality tech_innovator --votes 50 --output tech_eval.json --model claude-3-5-sonnet-20240620
```

## Model Personalities

The system includes three default personalities:

1. **EcoChampion**: Focuses on environmental impact and community contributions
2. **TechInnovator**: Prioritizes technical innovation and infrastructure development
3. **CommunityBuilder**: Emphasizes community growth, education, and inclusivity

You can modify existing personalities or add new ones by editing the `model_specs.py` file.

## Output Format

Results are saved as a JSON file with this structure:

```json
{
  "project_comparison": {
    "project1": {
      "name": "Project Name",
      "url": "Project URL",
      "category_scores": {
        "category1": 8,
        "category2": 7,
        "category3": 9,
        "category4": 6
      },
      "weighted_score": 7.5,
      "votes_allocated": 60,
      "vote_percentage": 60.0
    },
    "project2": {
      "name": "Project Name",
      "url": "Project URL",
      "category_scores": {
        "category1": 5,
        "category2": 6,
        "category3": 4,
        "category4": 5
      },
      "weighted_score": 5.0,
      "votes_allocated": 40,
      "vote_percentage": 40.0
    }
  },
  "decision_reasoning": "Detailed explanation of the vote allocation decision...",
  "total_votes_allocated": 100
}
``` 
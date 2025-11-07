use chrono::{DateTime, Utc};
use clap::Parser;
use git2::Repository;
use std::path::{Path, PathBuf};

const IGNORE_DIRS: &'static [&str] = &["target"];

#[derive(Parser, Debug)]
#[command()]
struct Cli {
    /// Path to the scratch repo root
    path: PathBuf,

    /// Filter output by language
    #[arg(long)]
    only_language: Option<String>,
}

#[derive(Clone, Debug)]
struct ProjectInfo {
    name: String,
    language: String,
    tags: Vec<String>,
    summary: String,
    last_modified: DateTime<Utc>,
}

impl ProjectInfo {
    fn from_dir(path: &Path) -> Self {
        let dir_name = path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();

        // Detect language based on project files
        let mut language = String::from("Unknown");
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries {
                if let Ok(entry) = entry {
                    let file_name = entry.file_name();
                    if file_name == "pyproject.toml" {
                        language = String::from("Python");
                        break;
                    } else if file_name == "Cargo.toml" {
                        language = String::from("Rust");
                        break;
                    } else if file_name == "index.html" {
                        language = String::from("HTML");
                        break;
                    } else if file_name.to_string_lossy().ends_with(".py") {
                        language = String::from("Python");
                    }
                }
            }
        }

        // Parse README.md
        let mut tags = Vec::new();
        let mut summary = String::new();

        let readme_path = path.join("README.md");
        if let Ok(contents) = std::fs::read_to_string(&readme_path) {
            let lines: Vec<&str> = contents.lines().collect();

            // Extract tags from YAML preamble
            if let Some(yaml_start) = lines.iter().position(|&l| l.trim() == "---") {
                if let Some(yaml_end) = lines
                    .iter()
                    .skip(yaml_start + 1)
                    .position(|&l| l.trim() == "---")
                {
                    let yaml_content = lines[yaml_start + 1..yaml_start + yaml_end + 1].join("\n");
                    if let Ok(yaml) = serde_yaml::from_str::<serde_yaml::Value>(&yaml_content) {
                        if let Some(yaml_tags) = yaml.get("tags") {
                            if let Some(tag_sequence) = yaml_tags.as_sequence() {
                                tags = tag_sequence
                                    .iter()
                                    .filter_map(|v| v.as_str())
                                    .map(|s| s.to_string())
                                    .collect();
                            } else if let Some(tag_str) = yaml_tags.as_str() {
                                tags = tag_str
                                    .trim_matches(|c| c == '[' || c == ']')
                                    .split(',')
                                    .map(|s| s.trim().trim_matches('"').to_string())
                                    .collect();
                            }
                        }
                    }
                }
            }

            // Extract first sentence as a summary
            // Detect first sentence after YAML preamble
            let content_after_yaml = if let Some(yaml_start) = contents.split("---").nth(2) {
                yaml_start.trim()
            } else {
                contents.as_str()
            };
            if let Some(first_para) = content_after_yaml.split("\n\n").next() {
                if let Some(pos) = first_para.find(|c| c == '.' || c == '?' || c == '!') {
                    summary = first_para[..=pos].trim().to_string();
                }
            }
        }

        let last_modified = match Repository::open(path) {
            Ok(repo) => {
                // Ensure repo lives long enough for us to get the info we need
                let head = repo.head().ok().unwrap();
                let commit = head.peel_to_commit().ok().unwrap();
                let timestamp = commit.time().seconds();
                DateTime::from_timestamp(timestamp, 0).unwrap_or_default()
            }
            Err(_) => path
                .metadata()
                .and_then(|m| m.modified())
                .map(|t| t.into())
                .unwrap_or_default(),
        };

        ProjectInfo {
            name: dir_name,
            language,
            tags,
            summary,
            last_modified,
        }
    }
}

fn print_project_list_item(project: &ProjectInfo) {
    println!(
        "- [{}]({}) - {} ({})",
        project.name, project.name, project.summary, project.language
    );
}

fn main() {
    let cli = Cli::parse();

    let mut project_info: Vec<ProjectInfo> = vec![];

    let result = std::fs::read_dir(cli.path).unwrap();
    for entry in result {
        if let Ok(entry) = entry {
            if entry.file_type().unwrap().is_dir() {
                if let Some(file_name) = entry.file_name().to_str() {
                    if !IGNORE_DIRS.contains(&file_name) && !file_name.starts_with('.') {
                        let info = ProjectInfo::from_dir(&entry.path());
                        project_info.push(info);
                    }
                }
            }
        }
    }

    // Filter by tag if specified
    if let Some(ref language) = cli.only_language {
        project_info = project_info
            .into_iter()
            .filter(|p| &p.language == language)
            .collect();
    }

    // Sort by last modified for recent projects
    let mut recent_projects = project_info.clone();
    recent_projects.sort_by(|a, b| b.last_modified.cmp(&a.last_modified));
    let recent_projects = &recent_projects[..5.min(recent_projects.len())];

    // Sort alphabetically for all projects
    let mut all_projects = project_info.clone();
    all_projects.sort_by(|a, b| a.name.cmp(&b.name));

    println!(include_str!("../preamble.md"));

    println!("## Last updated sketches\n");
    for project in recent_projects {
        print_project_list_item(&project);
    }

    println!("\n## All sketches\n");
    for project in all_projects {
        print_project_list_item(&project);
    }

    if cli.only_language.is_none() {
        println!("\n## Sketches by language");

        let mut languages: Vec<String> = project_info.iter().map(|p| p.language.clone()).collect();
        languages.sort();
        languages.dedup();

        for language in languages {
            println!();
            println!("### {}\n", language);
            let mut projects: Vec<&ProjectInfo> = project_info
                .iter()
                .filter(|p| p.language == language)
                .collect();
            projects.sort_by(|a, b| a.name.cmp(&b.name));

            for project in projects {
                print_project_list_item(project);
            }
        }
    }

    // Get all unique tags
    let mut all_tags: Vec<String> = project_info.iter().flat_map(|p| p.tags.clone()).collect();
    all_tags.sort();
    all_tags.dedup();

    if !all_tags.is_empty() {
        println!("\n## Sketches by tag");
        for tag in all_tags {
            println!();
            println!("### {}\n", tag);
            for project in &project_info {
                if project.tags.contains(&tag) {
                    print_project_list_item(project);
                }
            }
        }
    }
}

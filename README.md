# Robotics System

Welcome to the interactive course website for the "Robotics System" course.

This project is designed to provide a comprehensive learning platform that integrates multimedia courseware, interactive experiments, and project practice materials. It aims to facilitate a deep understanding of robotics systems by combining theoretical knowledge with practical applications.

---

## Project Overview

The "Robotics System" course website offers:

- **Multimedia Courseware:** Rich video lectures, slides, and reading materials to cover fundamental and advanced topics in robotics. These materials are curated by experts and updated regularly to reflect the latest advancements in the field.
- **Interactive Experiments:** Hands-on virtual labs and simulations that allow students to experiment with robotic algorithms and hardware concepts in a controlled environment. These experiments provide real-time feedback and encourage exploration and innovation.
- **Project Practice Materials:** Detailed project guidelines, datasets, and code repositories to support real-world robotics system development and research. Students can apply their knowledge by working on practical projects that simulate industry challenges.

---

## Innovative Learning Model

Our platform adopts a novel learning model that emphasizes:

- **Active Learning:** Encouraging students to engage actively with the content through interactive exercises, quizzes, and experiments. This approach helps reinforce concepts and improve retention.
- **Blended Theory and Practice:** Seamlessly integrating theoretical lessons with practical applications to reinforce understanding. Students can immediately apply what they learn in theory to hands-on activities.
- **Collaborative Projects:** Facilitating teamwork and knowledge sharing through project-based learning. Students can collaborate on projects, share insights, and develop communication skills essential for robotics engineering.

---

## Technical Highlights

- Responsive web design for accessibility across devices including desktops, tablets, and smartphones.
- Integration of multimedia content with interactive web technologies such as WebGL and real-time data visualization.
- Support for real-time experiment feedback and data visualization to enhance the learning experience.
- Modular architecture to easily extend course content and features, allowing for future scalability and customization.
- Secure user authentication and progress tracking to personalize the learning journey.

---

## Getting Started

To begin exploring the course materials, navigate through the sections provided on the website. Each module is designed to build upon the previous, ensuring a structured learning path. New users are encouraged to start with the introductory modules before progressing to advanced topics.

---

## Development & Deployment

### Prerequisites

Create a `.env` file in the project root (excluded from git) with the following keys:

```
COOLIFY_API_KEY=<your-coolify-api-key>
GITHUB_TOKEN=<your-github-personal-access-token>
```

Install local dependencies:

```bash
pip install mkdocs mkdocs-material plantuml-markdown jieba
```

### Local Preview

Start a local development server with live reload:

```bash
./preview.sh
```

The site will be available at **http://127.0.0.1:8000**.  
Any changes to files under `docs/` are reflected in the browser immediately.

### Deploy to Server

Once satisfied with local testing, deploy to the production server (Coolify):

```bash
python3 deploy_to_coolify.py
```

This script will:
1. Verify that required source files exist
2. Commit and push changes to GitHub
3. Locate the Coolify application
4. Trigger a forced rebuild and redeployment

The production site is served at **http://robotic.uwis.cn**.

### Project Structure

```
├── docs/                  # Markdown source files
│   ├── index.md           # Home page
│   ├── intro.md           # Course introduction
│   ├── syllabus.md        # Syllabus
│   └── resources.md       # References & resources
├── mkdocs.yml             # MkDocs configuration
├── Dockerfile             # Multi-stage build (MkDocs → nginx)
├── docker-compose.yaml    # Coolify deployment configuration
├── nginx.conf             # nginx serving configuration
├── preview.sh             # Local preview script
├── deploy_to_coolify.py   # One-command deployment script
├── .env                   # Secrets (not committed to git)
└── .gitignore
```

---

## Contribution and Feedback

We welcome contributions from the community to improve the course content and platform features. Please refer to the contribution guidelines on the website. For feedback or support, contact the course coordinator.

---

## Language Switch

This README is in English by default.  
You can switch to the Chinese version here: [README_cn.md](README_cn.md)

---

## Contact

For any questions, suggestions, or support, please contact the course coordinator at robotics-course@example.com.

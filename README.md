# “TrailHire” – An Outdoor Equipment Rental App

## Introduction

TrailHire is a new app designed to help customers browse and select outdoor equipment for rent. The company wants a fast, scalable, and secure system for managing user accounts and rental lists. You are tasked with building the account management and equipment rental functionality using a key-value database (Redis) and Python for the application layer.

---

### Core Requirements (Pass/Credit Level)

Students must implement the following:

**Key-Value Database Design (Redis):**

- Store user account details: username (email), password, first_name, security_question, and security_answer

- Store an equipment rental list for each user

- Create a set of security questions in Redis for random selection during account creation

**Python Application Features:**

- **Create Account:** Collect user details, randomly assign a security question, and store the account in Redis

- **Login:** Validate the username and password

- **Forgot Password:** Ask the assigned security question, validate the answer, and allow the user to reset their password

- **Manage Rental List:** After login, allow customers to:
  - Add equipment to their rental list
  - View their current rental list
  - Remove equipment from their rental list

- **Exit:** Return to the main menu or terminate the application

- **Initial Data Loader:** Load initial user accounts and sample equipment rental lists from a CSV file for testing

### Advanced Features (Distinction/HD Level)

Students can implement two or more of the following:

- **Password Hashing:** Use hashing (e.g., bcrypt or SHA256) before storing passwords

- **Activity Logging:** Log user actions, such as login attempts and changes to rental lists

- **GUI Interface:** Build a basic web-based interface using Flask

- **Equipment Catalogue and Inventory:**
  - Create a catalogue of equipment with rental prices and available quantities
  - Load the initial catalogue from a file
  - Allow customers to view available equipment, add items to their rental list, and update the inventory quantity

---

## Submission format

You should submit two documents:

### Report (Criteria 1)

Your report is to be presented as a professional business report. It must be submitted as a Word document (not pdf) with the following structure:

- Title page
- Table of contents
- Introduction
- Describing the system
  - Design
  - Outline the design of your key-value database
  - Discuss your reasons behind your design
- Testing
  - Discuss your testing plan
  - You should create test cases and show/discuss the results
- Future
  - Discuss any improvements you would make or explore in the future
- Reflection on Artificial Intelligence (AI) Use
  - Briefly explain how AI tools were used during the planning, development, debugging, testing, documentation, or report-writing stages.
  - Include:
    - The AI tool(s) used
    - At least three detailed prompts and a brief summary of the corresponding outputs
    - How each output was applied, modified, or rejected
    - Any errors, limitations, or unsuitable suggestions identified
    - How AI-generated content was checked, tested, and verified
    - Where relevant, screenshots of AI prompts and outputs can be included to illustrate your reflection

---

### Python program (Criteria 2 and 3)

The working Python program should be submitted as a single Python file.

This file should link to your database and perform the actions discussed above. Ensure you have provided access rights to your database, so it is accessible by other users (especially the markers!)

You should include documentation throughout the program.

You should include your testing and results. This should be in the form of automated test scripts to user test your functionality, or you can choose to do unit testing on some functions.

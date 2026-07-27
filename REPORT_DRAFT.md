# Project Report Draft

## Student Details

Name:

Roll Number:

Course: Application Development I

## Project Details

Project Name: Trekking Management Application

The project is a role-based web application for managing trekking events. The main roles are Admin, Trek Staff, and Trekker. The application helps an adventure organization manage treks, approve staff, assign staff to treks, track bookings, prevent overbooking, and maintain booking history.

## Problem Approach

I divided the application into three role-based dashboards. The Admin dashboard handles management tasks such as trek creation, staff approval, staff assignment, user/staff blacklisting, searching, and viewing bookings. The Staff dashboard allows approved staff members to manage only assigned treks. The Trekker dashboard allows users to search open treks, book treks, cancel bookings, and view history.

## Frameworks And Libraries Used

- Flask for backend routing and controllers
- Jinja2 for HTML templating
- Bootstrap for frontend styling
- SQLite for database
- Werkzeug security utilities for password hashing

## Database Design

Tables:

- `users(id, name, email, password_hash, role, phone, status, created_at)`
- `treks(id, name, location, difficulty, duration_days, available_slots, start_date, end_date, status, assigned_staff_id, description)`
- `bookings(id, user_id, trek_id, booking_date, status)`

Relationships:

- One staff user can be assigned to many treks.
- One trek can have many bookings.
- One trekker user can have many bookings.

## API Endpoints

No separate JSON API endpoints were implemented. The application uses Flask routes that render Jinja2 templates.

## AI/LLM Declaration

I used an AI coding assistant to help understand the project statement, scaffold the Flask application, and explain implementation steps. I reviewed the generated code and tested the main workflows locally.

## Presentation Video Link

Drive Link:

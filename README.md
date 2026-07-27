# Trekking Management Application

This is a simple Flask, Jinja2, Bootstrap, and SQLite project for the App Dev I trekking management problem statement.

## What The App Does

- Admin can manage treks, approve staff, blacklist users/staff, assign staff, search records, and view bookings.
- Trek Staff can login after approval, view assigned treks, update slots/status, and view participants.
- Trekkers can register, search open treks, book treks, cancel bookings, and view booking history.
- The app prevents booking when a trek is not open or when all slots are already booked.
- The SQLite database is created programmatically from `app.py`.

## Login Details

The admin user is created automatically when the app first runs.

- Email: `admin@trek.com`
- Password: `admin123`

## How To Run

1. Open a terminal in this project folder.

2. Create a virtual environment:

```bash
python3 -m venv .venv
```

3. Activate the virtual environment:

```bash
source .venv/bin/activate
```

4. Install Flask:

```bash
pip install -r requirements.txt
```

5. Start the Flask app:

```bash
flask --app app run --debug
```

6. Open this URL in your browser:

```text
http://127.0.0.1:5000
```

## Suggested Demo Flow

1. Login as admin using `admin@trek.com` and `admin123`.
2. Create one or two treks from Admin > Treks.
3. Register a staff account from the public register page.
4. Login as admin again and approve that staff account from Admin > Staff.
5. Assign the approved staff member to a trek from Admin > Assign Staff.
6. Login as staff and update the assigned trek's slots or status.
7. Register a trekker account.
8. Login as trekker, search open treks, and book one.
9. Login as admin and view the booking history.

## Project Structure

```text
app.py                  Main Flask application, routes, database setup
requirements.txt        Python dependency list
templates/              Jinja2 HTML templates
templates/admin/        Admin dashboard pages
templates/staff/        Trek staff dashboard pages
templates/user/         Trekker dashboard pages
static/style.css        Small custom CSS used with Bootstrap
```

## Database Tables

- `users`: stores admin, staff, and trekker accounts.
- `treks`: stores trek details such as location, difficulty, slots, dates, status, and assigned staff.
- `bookings`: stores trekker bookings and booking status.

## Notes For Viva

- Admin registration is not allowed. The admin is seeded automatically in `init_db()`.
- Staff registration starts with `pending` status and needs admin approval.
- Role-based access is handled by the `login_required()` decorator.
- Overbooking is prevented in the `/user/book/<trek_id>` route by counting active booked records before inserting a new booking.
- The project uses SQLite only, as required.

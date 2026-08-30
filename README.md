# Farmer Procurement Management Platform

This project is a Django-based farmer procurement platform designed to reduce queue congestion, improve transparency, and support a smoother procurement process between farmers, procurement centre staff, and administrators.

## Project Summary

The platform is being built in phases and currently focuses on the foundation layer that makes the rest of the system reliable:

- farmer-facing registration and login
- staff-only portal with protected access
- role-based authorization for farmers, staff, and admin
- profile management for both farmer and staff users
- public landing page for platform overview and portal entry

The app is intentionally structured to keep account logic stable before adding the procurement workflow itself.

## Product Vision

The platform should help farmers:

- register easily using mobile number
- update personal and location information
- move through a procurement journey without confusion
- stay informed about their process and status

It should help staff:

- access a dedicated staff portal
- manage procurement operations securely
- work in a role-specific environment separated from farmer access

It should help admin:

- create staff accounts safely
- manage platform-level operations and role access

## Current Project Architecture

### Role model

The app uses a custom Django `User` model with mobile as the primary login identity.

Roles:

- Farmer
- Staff
- Admin

Business logic is separated from Django’s default auth permission flags to keep clear role boundaries.

### Data model approach

- Shared authentication user: `User`
- Farmer-specific profile: `FarmerProfile`
- Staff-specific profile: `StaffProfile`

This keeps the system simple and avoids overloading one user record with large amounts of unrelated profile data.

### Account flow

Implemented and stable:

- public farmer registration
- farmer login and dashboard
- staff login and dashboard
- admin-only staff creation
- role enforcement on access
- farmer profile update form
- staff profile update form
- root public landing page

Not exposed publicly:

- public staff registration
- public admin registration

This is intentional and aligns with the project requirement that staff/admin onboarding should be controlled and secure.

## Features Completed

### 1. Custom authentication system

- mobile-based login
- custom `UserManager`
- role-based user creation and role checks
- admin, staff, and farmer role separation

### 2. Farmer onboarding

- farmer registration form
- location fields such as district and village
- automatic creation of `FarmerProfile`
- dashboard access restricted to farmers only

### 3. Staff onboarding and access

- staff accounts created through a protected admin flow
- staff login restricted to staff-only accounts
- dedicated staff dashboard and profile editing

### 4. Profile management

- farmer profile form for first name, last name, district, and village
- staff profile form for first name, last name, and designation
- profile updates saved to the related profile model and user record

### 5. Public landing page

- premium compact hero section
- platform overview cards
- portal entry links for farmer login and staff login
- professional layout designed as a product landing page

## Current Phase Status

### Phase 1 — Accounts and portal foundation complete

We have completed the account layer for the platform:

- custom farmer/staff/admin user roles
- farmer registration and login
- staff-only portal access
- admin-created staff accounts
- farmer and staff profile management
- public landing page and portal entry
- staff login root alias: /staff/login/ redirects to the staff login page (convenience alias)

### Next Phase — Procurement workflow in progress

Current work in this phase:

- farmer booking / procurement request flow
- queue handling and token generation
- staff processing dashboard
- procurement centre operations
- tracking and status updates

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` if you want to customize local Django settings.

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Recommended Next Feature Order

1. Farmer booking workflow
2. Staff queue dashboard
3. Procurement request status tracking
4. Admin monitoring view for staff/farmer activity
5. Optional notifications and reports

## Design and Architecture Notes

- Keep the app beginner-friendly.
- Use Django ORM for data handling.
- Avoid unnecessary complexity before workflow requirements are confirmed.
- Add external tools like payment, SMS, or live notifications only when needed by a real feature.

## Testing

The account module is already covered by Django tests for:

- user creation
- role checks
- login restrictions
- profile updates
- dashboard access rules

## Conclusion

The project has successfully moved past the initial auth prototype and is now in a clean, stable foundation stage for the real procurement workflow.

The account section is effectively complete and appropriate for the current product direction.

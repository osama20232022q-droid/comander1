# Study Commander Bot - Final Specification

## Product identity

A strict personal study-command Telegram bot for students. It plans, tracks execution, analyzes lectures, logs food/water/sleep, creates reports and certificates, and gates usage by admin-controlled paid subscriptions.

## Roles

### Admin
Configured through `ADMIN_IDS`.
Can:
- activate subscriptions
- stop subscriptions
- block/unblock users
- view user list
- view admin stats
- run full service demo

### Student
Can use features only with an active subscription:
- My Day
- Subjects
- PDF upload/analyze
- Pomodoro
- Food & Water
- Sleep/Routine
- Rescue Day
- Reports
- Certificates
- Demo mode if allowed by active access

## Subscription system

Stored in `subscriptions`.
Plans:
- 7-day trial
- monthly
- 3 months
- 6 months
- yearly

Middleware blocks unpaid students and shows ID + subscription request options.

## Railway

Long polling worker. No HTTP port required.
Recommended Railway volume:
- `/data/study_commander.sqlite3`
- `/data/uploads`
- `/data/certificates`

## Demo mode

`🧪 تجربة الخدمات` instantly populates private demo data:
- subject
- lecture
- sessions
- food/water logs
- discipline event
- routine experiment
- daily report
- student evaluation
- HTML certificate

## Medical student modules

- Anatomy
- Histology
- Embryology
- Biochemistry
- Cell genetics

PDF analysis estimates study time from density, images, lists/tables, level, and exam type.

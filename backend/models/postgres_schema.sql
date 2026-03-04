create extension if not exists "pgcrypto";

-- ═══════════════════════════════════════════════════════════
-- USERS TABLE — all authenticated accounts (admins + doctors)
-- Single source of truth for auth, role, and approval status
-- ═══════════════════════════════════════════════════════════
create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    full_name text not null,
    password text not null,
    role text not null default 'doctor' check (role in ('admin', 'doctor')),
    status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
    created_at timestamptz not null default now()
);

create index if not exists idx_users_email on public.users(email);
create index if not exists idx_users_role_status on public.users(role, status);

-- ═══════════════════════════════════════════════════════════
-- DOCTORS TABLE — doctor-specific profile (extends users)
-- ═══════════════════════════════════════════════════════════
create table if not exists public.doctors (
    id uuid primary key default gen_random_uuid(),
    user_id uuid unique not null references public.users(id) on delete cascade,
    specialty text not null,
    phone text,
    created_at timestamptz not null default now()
);

create index if not exists idx_doctors_user_id on public.doctors(user_id);

-- ═══════════════════════════════════════════════════════════
-- PATIENTS TABLE
-- ═══════════════════════════════════════════════════════════
create table if not exists public.patients (
    id uuid primary key default gen_random_uuid(),
    full_name text not null,
    date_of_birth date,
    email text unique,
    phone text,
    created_at timestamptz not null default now()
);

-- ═══════════════════════════════════════════════════════════
-- RECORDS TABLE — medical records linking doctors ↔ patients
-- ═══════════════════════════════════════════════════════════
create table if not exists public.records (
    id uuid primary key default gen_random_uuid(),
    doctor_id uuid not null references public.doctors(id) on delete cascade,
    patient_id uuid not null references public.patients(id) on delete cascade,
    diagnosis text not null,
    notes text,
    image_url text,
    status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
    recorded_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index if not exists idx_records_doctor_id on public.records(doctor_id);
create index if not exists idx_records_patient_id on public.records(patient_id);
create index if not exists idx_records_recorded_at on public.records(recorded_at desc);

-- ═══════════════════════════════════════════════════════════
-- PATIENT ↔ DOCTOR LINK TABLE
-- ═══════════════════════════════════════════════════════════
create table if not exists public.patient_doctors (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references public.patients(id) on delete cascade,
    doctor_id uuid not null references public.doctors(id) on delete cascade,
    assigned_at timestamptz not null default now(),
    unique (patient_id, doctor_id)
);

create index if not exists idx_patient_doctors_patient_id on public.patient_doctors(patient_id);
create index if not exists idx_patient_doctors_doctor_id on public.patient_doctors(doctor_id);

-- ═══════════════════════════════════════════════════════════
-- ANALYSIS RESULTS TABLE
-- ═══════════════════════════════════════════════════════════
create table if not exists public.analysis_results (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references public.patients(id) on delete cascade,
    doctor_id uuid not null references public.doctors(id) on delete cascade,
    disease text not null,
    probability numeric not null check (probability >= 0 and probability <= 1),
    severity text not null check (severity in ('low', 'moderate', 'high', 'critical')),
    risk text not null check (risk in ('low', 'medium', 'high')),
    uncertainty numeric not null check (uncertainty >= 0 and uncertainty <= 1),
    recommendations jsonb not null default '{}'::jsonb,
    follow_up_questions jsonb not null default '[]'::jsonb,
    sources jsonb not null default '{}'::jsonb,
    notes text,
    created_at timestamptz not null default now()
);

create index if not exists idx_analysis_results_patient_id on public.analysis_results(patient_id);
create index if not exists idx_analysis_results_created_at on public.analysis_results(created_at desc);

-- ═══════════════════════════════════════════════════════════
-- STORAGE BUCKET for medical images
-- ═══════════════════════════════════════════════════════════
insert into storage.buckets (id, name, public)
values ('medical-records', 'medical-records', true)
on conflict (id) do nothing;

-- ═══════════════════════════════════════════════════════════
-- SEED DATA
-- ═══════════════════════════════════════════════════════════
-- NOTE: You must ALSO create matching Supabase Auth users
-- (Dashboard → Authentication → Users → Add User) with the
-- same emails and passwords, otherwise login won't work.
-- ═══════════════════════════════════════════════════════════

-- ── 1. Admin user (approved, can login immediately) ──
-- Password: Admin@123
insert into public.users (id, email, full_name, password, role, status)
values (
    'a0000000-0000-0000-0000-000000000001',
    'admin@pulse.com',
    'Dr. Admin',
    'Admin@123',
    'admin',
    'approved'
) on conflict (email) do nothing;

-- ── 2. Approved doctor ──
-- Password: Doctor@123
insert into public.users (id, email, full_name, password, role, status)
values (
    'a0000000-0000-0000-0000-000000000002',
    'sarah.chen@hospital.com',
    'Dr. Sarah Chen',
    'Doctor@123',
    'doctor',
    'approved'
) on conflict (email) do nothing;

insert into public.doctors (id, user_id, specialty, phone)
values (
    'd0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000002',
    'Radiology',
    '+1-555-100-2001'
) on conflict (user_id) do nothing;

-- ── 3. Pending doctor (needs admin approval) ──
-- Password: Doctor@123
insert into public.users (id, email, full_name, password, role, status)
values (
    'a0000000-0000-0000-0000-000000000003',
    'james.w@hospital.com',
    'Dr. James Williams',
    'Doctor@123',
    'doctor',
    'pending'
) on conflict (email) do nothing;

insert into public.doctors (id, user_id, specialty, phone)
values (
    'd0000000-0000-0000-0000-000000000002',
    'a0000000-0000-0000-0000-000000000003',
    'Cardiology',
    '+1-555-100-2002'
) on conflict (user_id) do nothing;

-- ── 4. Another pending doctor ──
-- Password: Doctor@123
insert into public.users (id, email, full_name, password, role, status)
values (
    'a0000000-0000-0000-0000-000000000004',
    'maria.g@hospital.com',
    'Dr. Maria Garcia',
    'Doctor@123',
    'doctor',
    'pending'
) on conflict (email) do nothing;

insert into public.doctors (id, user_id, specialty, phone)
values (
    'd0000000-0000-0000-0000-000000000003',
    'a0000000-0000-0000-0000-000000000004',
    'Dermatology',
    '+1-555-100-2003'
) on conflict (user_id) do nothing;

-- ── 5. Sample patients ──
insert into public.patients (full_name, date_of_birth, email, phone)
values ('Alice Johnson', '1990-05-14', 'alice.j@email.com', '+1-555-200-3001')
on conflict (email) do nothing;

insert into public.patients (full_name, date_of_birth, email, phone)
values ('Bob Smith', '1985-11-22', 'bob.smith@email.com', '+1-555-200-3002')
on conflict (email) do nothing;

insert into public.patients (full_name, date_of_birth, email, phone)
values ('Carol Davis', '1978-03-08', 'carol.d@email.com', '+1-555-200-3003')
on conflict (email) do nothing;

-- ── 6. Link approved doctor to sample patients ──
insert into public.patient_doctors (patient_id, doctor_id)
select p.id, 'd0000000-0000-0000-0000-000000000001'
from public.patients p
where p.email in ('alice.j@email.com', 'bob.smith@email.com')
on conflict (patient_id, doctor_id) do nothing;

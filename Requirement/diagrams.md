# Diagrams — Application แปลผลเชื้อจุลินทรีย์

## 1. Process Flow

```mermaid
flowchart TD
    A[1 · Upload raw data<br/>CSV / XLSX wide worksheet]:::staff
    B[2 · Map template adapter<br/>LF07-05-22 / Petrifilm]:::sys
    C[3 · เลือกมาตรฐาน + กรอก V, n1, n2<br/>ISO / FDA / General + ช่วงนับ]:::staff
    D[4 · Interpretation engine<br/>คำนวณ + special cases + ปัดเศษ]:::sys
    E[5 · Fill Calculated / Results / Remark<br/>scientific notation, est., TNTC, Ratio]:::sys
    F[6 · Review บนเว็บ<br/>highlight special case / est.]:::approver
    G{7 · Approve ?}:::sys
    H[Approved → Export ไฟล์ผล<br/>lock + Approved by + audit trail]:::ok

    A --> B --> C --> D --> E --> F --> G
    G -- Reject → แก้ --> F
    G -- Approve --> H
    D -.เลือก mode.- M[ISO 7218 / FDA BAM / General]

    classDef staff fill:#E1F5EE,stroke:#0F6E56;
    classDef sys fill:#EEEDFE,stroke:#534AB7;
    classDef approver fill:#FAEEDA,stroke:#854F0B;
    classDef ok fill:#EAF3DE,stroke:#3B6D11;
```

## 2. Data Model (ER)

```mermaid
erDiagram
    Role ||--o{ User : has
    User ||--o{ Batch : uploads
    User ||--o{ ApprovalLog : acts
    Batch ||--o{ Sample : contains
    Batch ||--o{ ApprovalLog : tracked_by
    Sample ||--o{ DilutionRow : has
    Sample ||--|| Result : produces
    MethodConfig ||--o{ Sample : configures

    Role { int id PK; string name }
    User { int id PK; int role_id FK; string name; string email }
    Batch { int id PK; int uploaded_by FK; string file_name; string standard; float V; int n1; int n2; string status }
    Sample { int id PK; int batch_id FK; string lab_code; int replicate; string analyte; string method FK }
    DilutionRow { int id PK; int sample_id FK; int replicate_no; float dilution; string count_raw }
    Result { int id PK; int sample_id FK; string calculated; string result; string remark; string unit }
    ApprovalLog { int id PK; int batch_id FK; int actor_id FK; string action; string reason; datetime timestamp }
    MethodConfig { string method PK; string standard; float range_min; float range_max; string unit; int sig_figs }
```

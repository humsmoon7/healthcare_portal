🖥️ Prerequisites — Install These First
1. Install Python

Go to https://www.python.org/downloads/
Download Python 3.11 or later
✅ IMPORTANT: During install, check "Add Python to PATH"
Click Install Now

2. Install MySQL

Go to https://dev.mysql.com/downloads/installer/
Download MySQL Installer (Windows)
Run it, choose "Developer Default"
Set root password as: Student@12307 (to match the project)
Finish installation

3. Install VS Code (optional but recommended)

Go to https://code.visualstudio.com/
Download and install


📁 Step 1 — Download the Project from GitHub

Go to your GitHub repo link
Click the green "Code" button → "Download ZIP"
Extract the ZIP somewhere easy like C:\healthcare-portal


💻 Step 2 — Open Terminal

Press Windows + R, type cmd, press Enter
Navigate to the project folder:

cd C:\healthcare-portal

📦 Step 3 — Install Python Libraries
Run this command in the terminal:
pip install flask flask-cors mysql-connector-python pytz
Wait for everything to install.

🗄️ Step 4 — Set Up the Database
Open MySQL Command Line:

Search "MySQL Command Line Client" in Windows Start menu
Enter your root password: Student@12307

Run the SQL file:
sqlsource C:/healthcare-portal/database/Entire_DB.sql;
```
(adjust the path to wherever you extracted the project)

You should see a bunch of "Query OK" messages. That means it worked.

---

## ▶️ Step 5 — Run the Project

In your terminal (cmd), make sure you're in the project folder, then:
```
cd backend
python app.py
```

You should see:
```
* Running on http://localhost:5000
```

---

## 🌐 Step 6 — Open the App

Open any browser (Chrome, Edge) and go to:
```
http://localhost:5000
Login with:

Admin: admin / admin123
Staff: staff1 / staff123


🛑 How to Stop the App
Press Ctrl + C in the terminal.
▶️ How to Start Again Next Time
Just repeat Step 5 — open cmd, navigate to the backend folder, run python app.py.

⚠️ Common Issues
ProblemFixpip not recognizedReinstall Python and check "Add to PATH"Module not foundRun the pip install command againCan't connect to MySQLMake sure MySQL service is running (search "Services" in Windows, find MySQL, click Start)Port already in useRestart your computer and try againDatabase errorsMake sure you ran the SQL file correctly in MySQL

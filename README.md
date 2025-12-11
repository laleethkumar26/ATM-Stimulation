# 🏧 ATM Simulation System (Python + SQLite)

A console-based **ATM Machine Simulation System** built using **Python**, demonstrating key concepts like **Encapsulation**, **Inheritance**, and **Database Persistence** using **SQLite**.  
The project allows users to create accounts, authenticate securely, deposit/withdraw money, update PINs, and maintain balance history.

---

## 🚀 Features

### 🔐 User Authentication
- Login using **Account Number + PIN**
- Ability to create new accounts and set PIN securely
- Change PIN feature included

### 🏦 Core ATM Operations
- Balance Inquiry  
- Cash Withdrawal  
- Cash Deposit  
- Transaction History (session-based)  
- Persistent balance updates saved in the SQLite database

### 🧱 Technical Highlights
- **Encapsulation** → private balance and PIN attributes  
- **Inheritance** → `SavingsAccount` extends `Account`  
- **SQLite Integration** → persistent `atm_accounts.db` file storing account data  

---


# 📚 Documentation Index

Complete guide to all documentation files in this project.

---

## 🎯 Quick Navigation

**New User?** → Start with [START_HERE.md](START_HERE.md)  
**Just Want to Run It?** → Go to [QUICKSTART.md](QUICKSTART.md)  
**Setting Up Fresh?** → Read [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)  
**Need Help?** → Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 📖 All Documentation Files

### 1. [START_HERE.md](START_HERE.md)
**Purpose:** Central navigation hub  
**Read Time:** 5 minutes  
**Content:**
- Which guide to use for your situation
- Quick command reference
- Success checklist
- Learning path

**Start here if:** You're new to the project

---

### 2. [README.md](README.md)
**Purpose:** Project overview and quick reference  
**Read Time:** 2 minutes  
**Content:**
- Project description
- Quick start commands
- Available controllers
- Links to detailed docs

**Read this for:** Project overview

---

### 3. [QUICKSTART.md](QUICKSTART.md)
**Purpose:** Get running in 5 minutes  
**Read Time:** 5 minutes  
**Content:**
- Minimal installation steps
- Essential commands only
- Quick testing

**Use this when:** You want to run it NOW

---

### 4. [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
**Purpose:** Complete installation from scratch  
**Read Time:** 15 minutes  
**Content:**
- Step-by-step installation (8 steps)
- System requirements
- Verification procedures
- Troubleshooting per step
- WSL-specific notes
- Advanced configuration

**Use this when:** 
- First time setup
- Fresh Ubuntu installation
- Installation failed
- Need detailed explanations

---

### 5. [ARCHITECTURE.md](ARCHITECTURE.md)
**Purpose:** Understand how the system works  
**Read Time:** 20 minutes  
**Content:**
- Network topology diagrams
- Controller decision flow
- Algorithm explanations
- Data structures
- Packet flow examples
- Visual diagrams

**Read this to:**
- Understand the system design
- Learn the algorithms
- Modify/extend the code
- Debug complex issues

---

### 6. [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)
**Purpose:** Configuration and usage details  
**Read Time:** 10 minutes  
**Content:**
- How to run the system
- Configuration options
- Testing procedures
- Performance tips
- Helper scripts usage

**Use this for:**
- Day-to-day operations
- Reconfiguring settings
- Running tests
- Using helper tools

---

### 7. [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
**Purpose:** Fix common problems  
**Read Time:** As needed  
**Content:**
- Installation issues
- Runtime errors
- Testing problems
- Recovery commands
- Diagnostic procedures
- Emergency fixes

**Use this when:**
- Something doesn't work
- Error messages appear
- Need to reset/recover
- Debugging issues

---

## 🛠️ Script Files

### 1. [install.sh](install.sh)
**Purpose:** Automated installation  
**Usage:** `./install.sh`  
**What it does:**
- Installs all dependencies
- Creates virtual environment
- Installs Ryu with Python 3.12 fixes
- Verifies installation
- Provides next steps

**Run this:** For fresh installation

---

### 2. [test_setup.sh](test_setup.sh)
**Purpose:** Verify installation  
**Usage:** `./test_setup.sh`  
**What it checks:**
- Python installation
- Mininet availability
- Open vSwitch
- Virtual environment
- Ryu installation
- All controller files

**Run this:** After installation or when having issues

---

### 3. [run_controller.sh](run_controller.sh)
**Purpose:** Easy controller startup  
**Usage:** `./run_controller.sh <controller>.py`  
**What it does:**
- Activates virtual environment
- Starts specified controller
- Shows available options

**Run this:** Instead of typing full commands

---

## 🎓 Recommended Reading Order

### For Beginners
1. [START_HERE.md](START_HERE.md) - Orientation
2. [QUICKSTART.md](QUICKSTART.md) - Get it running
3. [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) - Understand setup
4. [ARCHITECTURE.md](ARCHITECTURE.md) - Learn how it works
5. [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) - Daily usage

### For Experienced Users
1. [README.md](README.md) - Quick overview
2. [QUICKSTART.md](QUICKSTART.md) - Commands
3. [ARCHITECTURE.md](ARCHITECTURE.md) - System design
4. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Keep handy

### For Troubleshooting
1. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - First stop
2. [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) - Reinstall if needed
3. [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) - Configuration issues

---

## 📊 Documentation Stats

| File | Size | Purpose | Priority |
|------|------|---------|----------|
| START_HERE.md | 6.8K | Navigation | 🔴 High |
| README.md | 2.3K | Overview | 🔴 High |
| QUICKSTART.md | 1.5K | Fast start | 🔴 High |
| INSTALLATION_GUIDE.md | 9.7K | Full setup | 🟡 Medium |
| ARCHITECTURE.md | 15K | Design docs | 🟢 Low |
| SETUP_INSTRUCTIONS.md | 3.3K | Configuration | 🟡 Medium |
| TROUBLESHOOTING.md | 4.3K | Problem solving | 🔴 High |

---

## 🔍 Find Information By Topic

### Installation
- Fresh install → [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- Quick install → [QUICKSTART.md](QUICKSTART.md)
- Automated → Run `install.sh`

### Running
- First time → [QUICKSTART.md](QUICKSTART.md)
- Daily use → [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)
- Helper script → Use `run_controller.sh`

### Understanding
- Overview → [README.md](README.md)
- Design → [ARCHITECTURE.md](ARCHITECTURE.md)
- Algorithms → [ARCHITECTURE.md](ARCHITECTURE.md)

### Problems
- Errors → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Install issues → [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) Troubleshooting section
- Runtime issues → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Configuration
- Settings → [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)
- Advanced → [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) Advanced section
- Customization → [ARCHITECTURE.md](ARCHITECTURE.md) + Code

---

## 💡 Documentation Tips

1. **Use Ctrl+F** - All docs are searchable
2. **Check multiple docs** - Some topics span multiple files
3. **Start simple** - Don't try to read everything at once
4. **Test as you read** - Try commands while reading
5. **Bookmark favorites** - Keep frequently used docs handy

---

## 📱 Quick Reference Card

```
┌─────────────────────────────────────────┐
│ ESSENTIAL COMMANDS                      │
├─────────────────────────────────────────┤
│ Install:    ./install.sh                │
│ Test:       ./test_setup.sh             │
│ Run Topo:   sudo python3 topo.py        │
│ Run Ctrl:   ./run_controller.sh XXX.py  │
│ Cleanup:    sudo mn -c                  │
│ Activate:   source venv/bin/activate    │
├─────────────────────────────────────────┤
│ ESSENTIAL DOCS                          │
├─────────────────────────────────────────┤
│ New?        START_HERE.md               │
│ Quick?      QUICKSTART.md               │
│ Problem?    TROUBLESHOOTING.md          │
│ Learn?      ARCHITECTURE.md             │
└─────────────────────────────────────────┘
```

---

## 🎯 Your Next Step

**Haven't started yet?**  
→ Read [START_HERE.md](START_HERE.md)

**Already installed?**  
→ Run `./test_setup.sh`

**Ready to run?**  
→ Follow [QUICKSTART.md](QUICKSTART.md)

**Want to understand?**  
→ Read [ARCHITECTURE.md](ARCHITECTURE.md)

**Having issues?**  
→ Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Last Updated:** November 2025  
**Maintained by:** Project Contributors

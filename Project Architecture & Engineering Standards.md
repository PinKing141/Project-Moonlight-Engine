Below is a **full AAA-level README** you can drop directly into your repo.
It explains the *entire architecture*, *its rules*, *its folder layout*, *its dependency flow*, *its debugging principles*, and *why these rules guarantee stability*.

Everything is written in clean UK English, with zero circular logic, clear guidance, and production-grade rationale.

---

# **README — Project Architecture & Engineering Standards (AAA-Grade)**

## **Overview**

This project is a **text-based, procedurally generated RPG engine** inspired by DnD.
It uses:

* **Python** for the game engine
* **MySQL** with the MySQL-RPG-Schema as the core persistent datastore
* **Open5e** as an external content provider for monsters, spells, abilities, and items
* A strict, layered **AAA game architecture** designed to prevent instability, circular imports, or cascading failures.

The goal is to provide a **flexible, expandable**, and **debug-friendly** foundation where new systems, mechanics, and content can be added without breaking existing subsystems.

This document describes the **folder structure**, **architectural rules**, **dependency flow**, **testing methodology**, and **engineering principles** that must be followed at all times.

Breaking these rules is considered a **critical violation** because it compromises engine stability.

---
Always make the game use arrow keys avoid making it use letters that is should be needed to

# **1. Project Structure (AAA Layered Architecture)**

```
rpg_project/
├─ src/
│  └─ rpg/
│     ├─ domain/
│     │  ├─ models/
│     │  ├─ services/ (pure logic only)
│     │  ├─ events.py
│     │  └─ repositories.py (interfaces only)
│     ├─ application/
│     │  ├─ services/ (game orchestration)
│     │  ├─ world_progression.py
│     │  ├─ encounter_generator.py
│     │  └─ dtos.py
│     ├─ infrastructure/
│     │  ├─ db/
│     │  │  ├─ mysql_connection.py
│     │  │  ├─ mysql_character_repo.py
│     │  │  ├─ mysql_entity_repo.py
│     │  │  └─ migrations/
│     │  ├─ open5e_client.py
│     │  ├─ caching.py
│     │  └─ logging_config.py
│     ├─ presentation/
│     │  ├─ cli.py
│     │  └─ renderers.py
│     └─ bootstrap.py
├─ db/
│  ├─ create_tables.sql
│  ├─ create_history_tables.sql
│  └─ seed_data.sql
├─ scripts/
│  ├─ import_open5e_monsters.py
│  └─ dev_seed_world.py
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ e2e/
└─ README.md
```

---

# **2. Architecture Philosophy**

This architecture follows four core principles:

### **2.1 Separation of Responsibilities**

Each layer has a *single purpose*:

* **Domain layer:** business rules, world mechanics, pure logic, no external calls
* **Application layer:** orchestration, use-cases, world tick logic
* **Infrastructure layer:** MySQL, Open5e, file I/O, caching, logging
* **Presentation layer:** CLI rendering, input handling
* **Bootstrap layer:** dependency injection and wiring

No layer is allowed to take on responsibilities belonging to another.

---

### **2.2 Dependency Rule (One Direction Only)**

Dependencies must only flow **downwards**:

```
presentation  →  application  →  domain  ←  infrastructure
```

**Domain never imports from application or infrastructure.
Application never imports concrete infrastructure.**

All infrastructure components must be injected through interfaces.

This rule is **non-negotiable** and is the main protection against:

* Circular imports
* Hidden coupling
* Runtime cascading failures
* Unpredictable behaviour
* Impossible-to-unit-test logic

---

### **2.3 Determinism and Reproducibility**

The game simulation must be reproducible:

* All random events seed off world state (turn number + location)
* All world changes generate domain events
* All domain events can be logged and replayed
* All DB writes produce a corresponding history entry

This ensures any bug can be reproduced exactly from logs or history tables.
AAA studios rely heavily on determinism for debugging; your engine must as well.

---

### **2.4 Expansion Without Collision**

Every new feature must be addable **without modifying existing systems**.

This is achieved through:

* Domain events
* Dependency injection
* Repository interfaces
* Strict modularity
* No shared mutable global state
* Procedural generation based on seeds (not randomness at runtime)

Adding content (monsters, quests, factions) must **never** require rewriting engine code.

---

# **3. Strict Engineering Rules**

These rules are absolute. Breaking them risks corruption, instability, or untestable behaviour.

---

## **Rule 1 — Domain Layer Must Stay Pure**

The domain layer may not:

❌ import SQLAlchemy
❌ import MySQL connectors
❌ import Open5e API client
❌ read files
❌ access the internet
❌ call print/input

The domain layer is the “laws of the world”.

It must remain deterministic, isolated, and reusable under any engine.

---

## **Rule 2 — Infrastructure Must Implement, Not Control**

Infrastructure may implement:

* Repositories
* Open5e content loader
* Logging
* Caching
* Migrations

It is not allowed to:

❌ contain business rules
❌ mutate world state directly
❌ generate encounters
❌ determine story progression

Those belong to the domain and application layers.

---

## **Rule 3 — Application Layer Orchestrates Everything**

The application layer:

✔ loads domain objects from repos
✔ applies domain logic
✔ produces domain events
✔ saves results
✔ triggers world ticks
✔ responds to player actions

But it must not:

❌ define core rules
❌ mutate DB structures
❌ reach into tables directly
❌ call external APIs except via infrastructure

---

## **Rule 4 — Presentation Layer Is Dumb**

Presentation:

✔ displays text
✔ collects player choices

It must not:

❌ contain mechanics
❌ store state
❌ query the DB
❌ call Open5e
❌ implement combat logic

This isolates the game logic from the interface.

---

## **Rule 5 — No Cyclical Dependencies**

Forbidden patterns:

```python
domain imports application
application imports infrastructure
infrastructure imports domain in a circular way
```

If you think you “need” to break this rule, you’re designing something incorrectly.

Use:

* interfaces
* event bus
* dependency injection

to solve coupling.

---

## **Rule 6 — World State Must Be Persisted Atomically**

A world tick must save:

* character changes
* entity changes
* location changes
* faction changes
* world timeline changes
* random seeds used

**All saved together, or not at all.**

Preventing partial state commits ensures the world cannot desynchronise or corrupt.

---

## **Rule 7 — Every Change Generates History**

The history tables from `create_history_tables.sql` are mandatory for debugging.

Any update to:

* character
* entity
* location
* faction
* world

must insert an entry in the corresponding history table.

This allows:

* replaying turns
* diagnosing broken states
* diffing changes
* performing rollbacks

AAA engines do this at scale; so should you.

---

## **Rule 8 — Randomness Must Be Seeded**

To ensure determinism:

```
seed = hash((world.turn, location.id, character.id, event_type))
```

Never call `random.random()` without seeding inside the engine.

Unseeded randomness makes bugs impossible to reproduce.

---

## **Rule 9 — All External Content Must Be Imported**

Open5e data may **not** be used directly during play.

It must be:

1. Fetched via the infrastructure client
2. Transformed into domain concepts
3. Inserted into your MySQL schema

This ensures:

* offline compatibility
* stable behaviour
* consistent testing
* future-proofing against API changes

---

## **Rule 10 — A Feature Must Never Break Other Features**

To enforce this:

* Features communicate only via events
* Events are handled by small, independent listeners
* Layers never bypass abstractions
* World logic is modular and subdivided

This prevents the “fix one bug, break five” effect.

---

# **4. Adding New Features Safely**

When adding:

* a new monster type
* a new quest logic
* a new faction
* a new world progression rule

You must follow this process:

### **Step 1 — Add the relevant data to the DB**

Monsters → `entity`
Attributes → `entity_attribute`
Items → `item`
Story flags → custom `world_flag` table if needed

### **Step 2 — Add domain logic (pure Python)**

Inside `domain/services`, define rules (no imports from infra).

### **Step 3 — Extend application orchestration**

Add a handler or event processor.

### **Step 4 — Register in bootstrap**

Wire the new handler into the event bus.

### **Step 5 — Write tests**

* Unit tests for domain
* Integration tests for repositories
* Replay tests using history tables

### **Step 6 — Confirm determinism**

Re-run tests twice and compare outputs.

---

# **5. Debugging & Stability Framework**

### **5.1 Snapshot System**

Every world tick must support generating a “snapshot” (JSON) of:

* world state
* character state
* random seeds
* event queue

Snapshots allow:

* rollback
* comparison
* regression detection

---

### **5.2 History Replay**

Using the history tables, you can reconstruct:

```
turn 1 → state A  
turn 2 → state B  
turn 3 → state C  
```

If something breaks, replay logs until the divergence appears.

---

### **5.3 Isolation of Components**

Because each subsystem is isolated:

* Combat cannot break inventory
* Inventory cannot break factions
* Factions cannot break locations
* Procedural generation cannot break the DB

This is why the architecture is strict.

---

# **6. Why This Architecture Prevents Constant Breakage**

### **✔ No circular imports**

→ eliminates runtime errors and hidden coupling.

### **✔ Deterministic RNG**

→ makes simulation reproducible and debuggable.

### **✔ History snapshots for every change**

→ you can always find the exact moment a bug happened.

### **✔ Domain isolation**

→ logic stays pure and testable.

### **✔ Infrastructure is replaceable**

→ you can swap MySQL → PostgreSQL later without rewriting gameplay.

### **✔ Application orchestration prevents chaos**

→ all features run through consistent pipelines.

### **✔ Adding features does not affect existing ones**

→ no domino effect when fixing bugs.

### **✔ World state commits atomically**

→ avoids corrupted saves.

### **✔ External content is imported, not used live**

→ no dependency on unstable third-party APIs.

---

# **7. Conclusion**

This README defines the **non-negotiable engineering rules** of the engine.

Following them guarantees that you will have:

* a stable foundation
* easy extensibility
* safe debugging
* modular development
* reproducible simulation
* professional-grade reliability

This is the same style of architecture used in large-scale studios because it works and scales for decades.



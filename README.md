# 🦥 Sloth Fridge

**Take one photo of your fridge. Get a shopping list. Nothing leaves your laptop.**

Built for Hacktoberfest Week 3: *Slow and Steady*.

---

## The idea

You open the fridge, take one photo, close the door again. While you are at work, a small AI model
that runs on your own computer looks at the photo, works out what you have, compares it with what
you had last time, and notices what has run out. By the time you get home, there is a tidy
shopping list waiting for you.

You never stand in front of an open fridge again. You never pay for it either.

```
$ sloth-fridge scan fridge.jpg
scanned fridge.jpg -> 19 item(s)
   - milk x4 container [dairy] (seen in 2 views)
   - mayo x2 container [condiment] (seen in 2 views)
   - tomato ketchup x4 container [condiment] (seen in 2 views)
   - yogurt x1 container [dairy] (seen in 2 views)
   ...

DAIRY
  [ ] milk x2 container  (running low, 1 container left)
  [ ] yogurt x2 container  (running low, 1 container left)

$ sloth-fridge digest
chicken, eggs, cheese, ice cream, more yogurt
fridge smells like old mustard and hot sauce
```

---

## Why open source matters here

This project only works because the AI parts are open. Here is what that buys us, in plain terms.

### It works with no internet

Everything runs on [Ollama](https://ollama.com), with two open weight models on your own GPU:
`qwen2.5vl:3b` for looking at the photo and `qwen2.5:3b` for turning notes into a list.

There is no API key, no account, no token and no bill. Pull the models once and the tool works on
a plane, in a basement, or on a cheap second hand laptop.

A closed API cannot do this. It charges you per photo, it needs a working internet connection,
and if the company shuts down the model your tool is dead. An open model is just a file on your
disk. You keep it forever. You can swap it any time.

```bash
ollama pull qwen2.5vl:3b   # looks at the photo, about 3.2 GB
ollama pull qwen2.5:3b     # writes the list, about 2.0 GB
```

### Your fridge stays on your fridge

A photo of your fridge tells people a lot. Your diet, your money, your health, your family, and
the drawer you keep locked. Uploading it to a closed API means sending it to a company you do not
control, over a network you do not control, and keeping it there under rules you did not write.

Here, the tool makes exactly one network call, and that call goes to `127.0.0.1:11434`, which is
your own Ollama process on your own machine. The database is a SQLite file in your own user
folder. Your photos are never uploaded and never seen by anyone but you.

You can check this yourself:

```bash
grep -rn "https\?://" sloth_fridge/     # one hit only: 127.0.0.1:11434
```

### Set it up once, never pay again

After the first model download, the cost of a fridge scan is zero. Just electricity and a little
GPU time. You can scan every single day for years and the bill is still zero.

With a paid API, the thing you would use most, which is scanning all the time, is exactly the
thing that costs the most.

### Open weights let us fix the mistakes

`qwen2.5vl:3b` is a small model. It is not perfect. On the first try it told me the fridge
contained "jalapeno jelly, unspecified bottle, unspecified bottle, unspecified bottle..." twenty
times in a row. It had made the same thing up over and over.

We could not have fixed that with a closed API. But because the model is a local, open weight
checkpoint, we can build around it:

* **We cut the photo into small overlapping tiles.** A carton hiding in the back of a shelf is
  easy to miss in one wide photo, but easy to spot in a close up.
* **We let the model talk instead of making it fill in a form.** Asking for raw JSON made the
  model loop and make things up. Asking it the same question in plain English gave us
  "Mustard, Ketchup, Hot sauce, Pickles, Kikkoman soy sauce, Honey", which was all really in the
  photo. So the vision model describes, and the text model takes notes.
* **We check the answer.** Anything seen in only one tile gets asked about again with a simple
  yes or no question.
* **We filter in plain Python.** Brand names, pack sizes, units and vague labels like
  "yellow lid" are handled by regular code, not by the model. This part works with any model, so
  changing models does not break it.

This is the bit a closed model would have made impossible. When a better open model comes out,
you change one environment variable and everything keeps working.

### It is yours

The models, the prompts, the rules and the database are all readable and editable. The list of
things you always keep stocked is a JSON file you own:

```json
{ "canonical": "milk", "unit": "container", "threshold": 1, "buy_qty": 2, "category": "dairy" }
```

Nobody can change what ends up on your shopping list, because there is no app running on someone
else's server.

---

## How it works

```
  fridge photo
       |
       |--> split into small overlapping tiles, plus the whole picture
       |         |
       |         |--> qwen2.5vl:3b  "describe what you can see"   (once per tile)
       |         |         |--> plain English notes
       |         |
       |         |--> qwen2.5:3b    "turn these notes into items"  (once per tile)
       |                   |--> name, amount, unit, type, how sure the model is
       |
       |--> normalise.py    clean up names, units and types, throw away vague labels
       |
       |--> voting           an item seen in 3 tiles beats an item seen in 1
       |
       |--> check            items seen once get a yes or no question
       |
       |--> planner.py       compare with the last scan, check the staples,
                            work out what is missing, sort it by shop aisle
```

Everything is plain Python and SQLite. No vector database, no agent framework, no cloud anything.

---

## Install

### 1. Ollama, the local AI server

```bash
winget install --id Ollama.Ollama -e              # Windows
brew install ollama                              # macOS
curl -fsSL https://ollama.com/install.sh | sh     # Linux
```

### 2. The open weight models

```bash
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:3b
```

### 3. Sloth Fridge

```bash
git clone https://github.com/<you>/sloth-fridge.git
cd sloth-fridge
pip install -e .                      # or: pip install -e ".[ui,dev]" for the web UI and tests
```

Check that everything is ready:

```bash
sloth-fridge doctor
```

```
data dir : C:\Users\PC\AppData\Local\SlothFridge
ollama   : http://127.0.0.1:11434 (v0.40.5)
models   : qwen2.5:3b, qwen2.5vl:3b
vision   : qwen2.5vl:3b -> present
text     : qwen2.5:3b -> present

Everything runs on this machine. No photo leaves your computer.
Set OLLAMA_NO_CLOUD=1 to keep Ollama fully offline.
```

---

## How to use it

### Scan a photo

```bash
sloth-fridge scan fridge.jpg
sloth-fridge scan ~/Pictures/fridge/          # a whole folder
```

### See the list

```bash
sloth-fridge list                              # sorted by supermarket aisle
sloth-fridge list --format markdown            # a checklist you can paste anywhere
sloth-fridge list --format json                # for scripts
sloth-fridge export ~/shopping-list.md
```

```
DAIRY
  [ ] butter x2 pack  (out of stock)
  [ ] milk x2 container  (running low, 1 container left)
  [ ] yogurt x2 container  (running low, 1 container left)
```

### Tick things off, by hand or with a receipt

```bash
sloth-fridge bought eggs
sloth-fridge add "chocolate ice cream" -q 1 -u container
sloth-fridge receipt receipt.jpg               # reads the receipt and ticks items off for you
```

Reading a receipt also puts everything you bought into the pantry, so the list does not ask for
milk again straight after you bought milk.

### The two line morning summary

```bash
sloth-fridge digest
```

```
chicken, eggs, cheese, ice cream, more yogurt
fridge smells like old mustard and hot sauce
```

### Use up what is about to go off

```bash
sloth-fridge plan
```

```
Chicken Salad Sandwich - mayo, chicken, bread, lettuce, tomato
Mango Salsa - mango, onion, lime, cilantro
Stir-Fried Veggies - broccoli, onion, garlic, soy sauce, hot sauce, sesame oil
```

### Let it run while you sleep

```bash
sloth-fridge watch ~/Pictures/fridge-inbox
```

Any new photo that lands in the folder gets scanned automatically. Pair this with a scheduled
task and the list is simply there in the morning:

```powershell
# Windows Task Scheduler, every day at 07:00
$action  = New-ScheduledTaskAction -Execute "sloth-fridge" -Argument "scan C:\Users\PC\Pictures\fridge"
$trigger = New-ScheduledTaskTrigger -Daily -At 7am
Register-ScheduledTask -TaskName "SlothFridge" -Action $action -Trigger $trigger
```

### Web version

```bash
streamlit run sloth_fridge/ui.py
```

Upload a photo, watch the list rebuild, download it as markdown.

---

## All the commands

| Command | What it does |
| --- | --- |
| `doctor` | check Ollama, the models and your data folder |
| `init` | create the local database |
| `scan <paths>` | inventory a fridge photo or a folder of photos |
| `receipt <paths>` | read a receipt and tick bought items off |
| `list` | show the shopping list (`--format plain\|markdown\|json`) |
| `add <name>` | add an item by hand |
| `bought <name>` | tick an item off |
| `rm <name>` | remove an item |
| `clear` | empty the list |
| `pantry` | show the last fridge snapshot |
| `staples` | show how close each staple is to running out |
| `digest` | two line morning summary |
| `plan` | meals that use up what is about to spoil |
| `export <file>` | write the list to a markdown file |
| `watch <dir>` | watch a folder and scan new photos as they arrive |

---

## Settings

Everything lives in one folder. On Windows that is `%LOCALAPPDATA%\SlothFridge`, on other systems
it is `~/.local/share/sloth-fridge`.

| File | What it is for |
| --- | --- |
| `sloth_fridge.db` | SQLite, holds the pantry, the shopping list and photo history |
| `staples.json` | the things you always keep stocked, and how low you let them get |
| `config.json` | optional extra settings |

Environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | where your local AI server lives |
| `SLOTH_VISION_MODEL` | `qwen2.5vl:3b` | any vision model Ollama can serve |
| `SLOTH_TEXT_MODEL` | `qwen2.5:3b` | any text model Ollama can serve |
| `SLOTH_FRIDGE_HOME` | platform data folder | where the database and staples live |
| `SLOTH_MAX_IMAGE_EDGE` | `1024` | how much we shrink the photo before the model sees it |
| `OLLAMA_NO_CLOUD` | not set | set to `1` to make sure Ollama never phones home |

---

## How accurate is it, honestly

`qwen2.5vl:3b` has 3 billion parameters and runs on a normal home graphics card. It is good
enough to be genuinely useful and cheap enough to be free, but it is not a food recognition
system.

It is good with condiments, jars, bottles and any fruit or vegetable that is easy to see. It
struggles with small things that are hidden, like one egg behind a bottle, or anything behind
glass.

The multi tile voting and the yes or no check get rid of most of the nonsense, but you will still
get a few odd entries. That is why every item shows the reason it was added, so you can see
exactly why the tool thinks you need milk and disagree with it.

Want better results? Use a bigger open model. Nothing in the code changes:

```bash
ollama pull qwen2.5vl:7b
SLOTH_VISION_MODEL=qwen2.5vl:7b sloth-fridge scan fridge.jpg
```

That is the whole point of doing this in the open.

---

## Project layout

```
sloth_fridge/
  ollama_client.py   talks to the local AI server, for both vision and text
  extractor.py       describe, then extract, then check. Multi tile voting lives here
  imaging.py         loading photos, cutting them into tiles, parsing messy JSON
  normalize.py       cleaning up names, units and types, throwing away vague labels
  store.py           SQLite: photos, pantry, shopping list, staples
  planner.py         comparing scans, restock rules, sorting by aisle, printing
  digest.py          the two line morning summary and the use it up plan
  cli.py             the command line
  ui.py              the web version
scripts/
  demo.py            runs the whole thing on the sample photos
  make_receipt.py    draws the fake receipt used by the demo
tests/               40 tests, no AI model needed
sample_photos/       demo photos and a fake receipt (see CREDITS.md)
```

## Tests

```bash
pytest
```

The tests cover the parts that are just logic, which means normalising, the database, the
planner and the JSON parser. They need no model and no internet connection.

---

## Models and licences

| Part | Model | Licence |
| --- | --- | --- |
| Vision | `qwen2.5vl:3b` | Apache-2.0 |
| Text | `qwen2.5:3b` | Apache-2.0 |
| AI server | Ollama | MIT |
| Demo photos | Wikimedia Commons | CC BY 4.0 and public domain |

## Licence

MIT. See [LICENSE](LICENSE).

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

I built **Sloth Fridge**. You take one photo of your fridge and it gives you a shopping list.

Here is the chore it removes. You open the fridge, the cold air is on your legs, you are staring at half a lemon and a tub of something, and you are trying to remember what you already bought. Then you write a list on your phone, you forget half of it in the shop, and you come home with three bags of the same thing.

Now you take one photo and close the door. While you are out, a small AI model that runs on your own laptop looks at the photo, works out what you have, compares it with what you had last time, and tells you what has run out. When you get home, the list is waiting for you.

It also reads your shopping receipt. Everything on the receipt gets ticked off and added to your pantry, so the list does not ask for milk right after you bought milk.

The people who get to be lazy here are anyone who shops. It is most useful for people who cook at home and shop for one or two people, because those are the people who end up buying the same six things every week.

## Demo

There is no live link and no video, because the whole point is that it runs on your own machine and there is nothing to host.

The repo has four real fridge photos and a sample receipt. You can run the whole thing on your laptop with one command:

```bash
git clone https://github.com/sonu7089/sloth-fridge.git
cd sloth-fridge
pip install -e .
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:3b
python scripts/demo.py
```

This is real output from my machine. It scanned four fridge photos in about 40 seconds each and printed the list:

```text
scanning fridge-01-inside-double-sided-refrigerator.jpg ...
  19 item(s) in 56s
    - hot sauce x4 piece [condiment]
    - mustard x2 container [condiment]
    - mayo x2 pack [condiment]
    - yogurt x1 container [dairy]
    - milk x3 container [dairy]
    - soy sauce x2 container [condiment]
    - tomato ketchup x1 container [condiment]
    - eggs x6 pack [eggs]
    - bread x1 loaf [bread]
    - cheese x1 pack [dairy]
    ...

DAIRY
  [ ] butter x2 pack  (out of stock)
  [ ] milk x2 container  (running low, 1 container left)
  [ ] yogurt x2 container  (running low, 1 container left)

Morning digest
corn, cucumber, lemon, hot sauce
fridge smells like a tropical fruit salad
```

Then it reads the receipt and everything on it is ticked off:

```text
bought milk
bought yogurt
bought eggs
bought cheese
bought bread
bought banana
bought lime
bought olive oil
bought tomato ketchup
bought black pepper
bought coffee
```

You can also drive it from the command line:

```bash
sloth-fridge scan fridge.jpg          # scan a photo
sloth-fridge list                      # show the list
sloth-fridge digest                    # two line morning summary
sloth-fridge receipt receipt.jpg       # read a receipt
sloth-fridge watch ~/Pictures/fridge   # scan new photos as they arrive
```

There is a web version too:

```bash
streamlit run sloth_fridge/ui.py
```

## Code

{% embed https://github.com/sonu7089/sloth-fridge %}

https://github.com/sonu7089/sloth-fridge

It is plain Python and SQLite. Here is the map of the repo:

```text
sloth_fridge/
  ollama_client.py   talks to the local AI server
  extractor.py       the describe, extract and check pipeline
  imaging.py         loads photos, cuts them into tiles, parses messy JSON
  normalize.py       cleans up names, units and types, throws away vague labels
  store.py           SQLite: photos, pantry, shopping list, staples
  planner.py         compares scans, restock rules, sorts by shop aisle
  digest.py          the two line summary and the meal plan
  cli.py             the command line
  ui.py              the web version
tests/               40 tests, no model needed
```

The part I am happiest with is the extractor. It is about 200 lines and it is the reason a 3B model becomes usable:

```python
def extract_fridge_items(client, image_payload, model=None, options=None):
    options = options or ScanOptions()
    views = crop_views(image_payload, grid=options.grid, include_full=options.include_full)
    votes = {}

    for label, payload in views:
        description = _describe(client, model, payload)
        items = _extract_from_text(client, description, options.text_model)
        _merge_votes(votes, items, label)

    if options.verify:
        for vote in votes.values():
            if vote.views == 1:
                vote.verified = _verify(client, model, views[0][1], vote.canonical)

    return _finalize(votes, options)
```

## How I Built It

These are the open source parts I used:

- **Ollama** runs the models locally on my RTX 4060.
- **qwen2.5vl:3b** looks at the photo. Apache 2.0, about 3.2 GB.
- **qwen2.5:3b** turns notes into a shopping list. Apache 2.0, about 2 GB.
- **Pillow** cuts the photo into tiles.
- **SQLite** holds the pantry and the list.

Here is the thing that took me the longest, and it is the reason this project works at all.

`qwen2.5vl:3b` is a small model. When I asked it for JSON straight away, it broke. It made up one item and then repeated it twenty times:

```json
{"items": [{"name": "jalapeno jelly", "qty": 1}, {"name": "jalapeno jelly", "qty": 1}, ...]}
```

It was not really looking at the photo either. The fix was three things.

**One, let the model talk instead of making it fill in a form.** I asked the same question in plain English, "look at this photo of a refrigerator shelf and tell me which food you can actually see", and the answer changed completely. It gave me "Mustard, Ketchup, Hot sauce, Pickles, Kikkoman soy sauce, Honey", and all of those really were in the photo. So now the vision model writes notes and the text model takes notes. Two jobs, two models.

**Two, cut the photo into small tiles.** A small carton at the back of a shelf is invisible in one wide photo. So I cut the photo into a 3 by 3 grid of overlapping tiles and look at each one. Then the votes decide. An item that shows up in three tiles is real. An item that shows up in one tile gets asked about again.

**Three, do the boring work in normal Python.** Brand names, pack sizes, units and vague answers like "yellow lid" are handled by code, not by the model. The model gives me "Kikkoman soy sauce", the code turns that into "soy sauce", and "free range eggs 12" becomes "eggs".

The rule I ended up with is simple. The model is good at seeing. It is bad at formats and bad at counting. So let it see, and let the code do the rest.

After all of that, a scan takes about 40 seconds on my laptop.

## Why Does Open Innovation Matter?

Open is the reason this project is possible, not just nice to have.

**It works with no internet.** There is no API key and no bill. Pull the two models once and the tool works on a plane or on a cheap second hand laptop. A closed vision API charges you for every photo and needs a working connection every time.

**Your fridge stays on your fridge.** A photo of your fridge tells people your diet, your money, your health and your family. Uploading it to a company you do not control means sending it somewhere you do not control. My code makes exactly one network call and it goes to `127.0.0.1`, which is my own Ollama process. You can check that yourself:

```bash
grep -rn "https\?://" sloth_fridge/
# config.py:50: OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
```

**It costs nothing to run.** After the first download the cost of a scan is zero, so I can scan every single day. With a paid API, the thing I would use most is the thing that costs the most.

**I could fix the model because the model was a file.** The hallucination loop above was not a support ticket. I changed the prompt, I changed the sampling, I built a whole pipeline around it, and I can try a different checkpoint with one command:

```bash
SLOTH_VISION_MODEL=qwen2.5vl:7b sloth-fridge scan fridge.jpg
```

With a closed API I can only change the prompt. With an open model I can change how the model is used.

**It is mine.** The list of things I always keep stocked is a JSON file I own. Nobody can change what ends up on my shopping list, because there is no app running on someone else's server.

To be honest, a big closed model would read a fridge photo better than a 3B model does. What open wins for me here is privacy, cost, and the fact that I can fix it myself.

## My Agent Session

{% agent_session 1059 %}

## The Lazy Payoff

Here is the honest version.

A scan takes about 40 seconds of GPU time and about 10 seconds of my time. The thing it replaces is standing in a cold kitchen with the fridge door open, trying to remember what is already in there.

The part I like most is not the scan. It is the receipt step. I buy milk, I take a photo of the receipt, and the list fixes itself. Before this I would come home, put the bags away, and still have no idea what was in the fridge before the shop.

I did not run this for a full week of shopping, so I do not have a perfect number. What I can say is that on the four real fridge photos and the receipt I tested it with, it found the condiments, dairy, eggs and fruit correctly every time, and writing the whole shopping list took about 10 seconds.

## Thanks for participating

<!-- Team Submissions: Please pick one member to publish the submission and credit teammates by listing their DEV usernames directly in the body of the post. -->

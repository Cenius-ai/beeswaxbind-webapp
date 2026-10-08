# Using BeeswaxBind

Every example below is a real, copy-pasteable command. `python3 beeswaxbind.py`
can be shortened to `beeswaxbind` if you ran `bash install.sh`.

## 1. Which harness needle carries my thread?

```bash
python3 beeswaxbind.py needle --thread 18/3 --leather 4oz
```

```
inputs
  thread          18/3 (3 ply, 0.65 mm (0.026 in), 15 lb (6.8 kg) break)
  leather         4 oz (1.6 mm)
  units           both

recommendation
  primary         harness needle 1.40 mm (US 3)
  alternate       harness needle 1.20 mm (US 4)
  needle length   48.00 mm (1.89 in) / 45.00 mm (1.77 in)

rationale
  why             thread 18/3 (0.65 mm) takes harness needle 1.40 mm (US 3); the eye clears the thread without opening the seam on 4 oz (1.6 mm) leather
```

* The **primary** needle is the closest fit for the thread's diameter, with a
  small allowance that grows with leather weight; the **alternate** is the next
  bracket, for when the eye is tight or the leather is unforgiving.
* Leather weight accepts ounces (`4oz`, `6`) or thickness (`2mm`, `1.6mm`) and
  must be between 2 and 20 oz (0.8–8 mm). Given millimetres, the ounce equivalent
  is printed next to it, and vice versa.
* With no `--leather`, 4 oz is assumed and the assumption is printed:

```bash
python3 beeswaxbind.py needle --thread 25/3
# assumptions
#   assumed         4 oz leather assumed (default)
```

* One system only, for a workshop note:

```bash
python3 beeswaxbind.py needle --thread 18/3 --units metric     # 1.40 mm, 1.20 mm
python3 beeswaxbind.py needle --thread 18/3 --units imperial   # US 3, US 4
```

* `--color auto` (the default) paints the single accent - `#b26232` - on the
  `primary` and `verdict` lines only when stdout is a real terminal, so files,
  pipes and logs stay plain. `NO_COLOR=1`, `--color never` and `--color always`
  are honoured.

* Unknown thread numbers list what the bundled table knows:

```bash
python3 beeswaxbind.py needle --thread 99/9
# stderr: beeswaxbind: error: unknown thread number '99/9'; known thread numbers are
#         12/3, 16/3, 18/3, 18/4, 25/3, 25/4, 30/3, 35/3, 40/3, 45/3, 60/3, 80/3
# exit code 2
```

## 2. What stitch length does a stitch density give me?

```bash
python3 beeswaxbind.py tension --spi 6
```

```
inputs
  stitch density  6.00 spi
  stitch length   4.23 mm (0.17 in)
  thread          18/3 (3 ply, 0.65 mm (0.026 in), 15 lb (6.8 kg) break)
  leather         4 oz (1.6 mm)
  needle          harness needle 1.40 mm (US 3)
  units           both

tension verdict
  verdict         standard
  reason          6.00 spi sits inside the 6-8 spi band for thread 18/3 and harness needle 1.40 mm (US 3) on 4 oz (1.6 mm) leather

assumptions
  assumed         thread 18/3 and 4 oz leather assumed (defaults)
```

* Start from either side of the conversion:

```bash
python3 beeswaxbind.py tension --length 4mm          # 6.35 spi
python3 beeswaxbind.py tension --spi 8 --leather 2oz # shorter, lighter work
python3 beeswaxbind.py tension --spi 4 --leather 14oz
```

* The verdict is **tight** above the band for that leather weight, **loose**
  below it, and **standard** inside it — the band moves with the leather, from
  6–8 spi on 2–5 oz up to 2–4 spi on 16–20 oz.
* `--thread` and `--leather` default to 18/3 and 4 oz, and the `assumptions`
  block always says so.

## 3. How much beeswax and rosin for this batch?

```bash
python3 beeswaxbind.py wax --parts 5:1 --batch 100g
```

```
blend
  component  weight            share
  ---------  ----------------  -----
  beeswax    83.3 g (2.94 oz)  83%
  rosin      16.7 g (0.59 oz)  17%
  total      100 g (3.53 oz)   100%
```

* The batch can be given in grams or ounces: `--batch 50`, `--batch 50g`,
  `--batch 2oz`. With no `--batch`, 50 g is assumed and stated:

```bash
python3 beeswaxbind.py wax --parts 5:1
# beeswax 41.7 g / rosin 8.3 g, and "50 g batch assumed (default)"
```

* Named recipes carry their own ratio and a note on where they suit:

```bash
python3 beeswaxbind.py wax --preset soft      # 5:1, everyday hand sewing
python3 beeswaxbind.py wax --preset standard  # 4:1
python3 beeswaxbind.py wax --preset hard      # 3:1, coarse thread, heavy harness
```

* Bad input is one line on stderr and exit code 2:

```bash
python3 beeswaxbind.py wax --parts 5:0
# error: both beeswax and rosin parts must be greater than zero
python3 beeswaxbind.py wax --batch abc
# error: batch weight must be a positive number such as 50 or 50g
```

## 4. Browse and search the bundled tables

```bash
python3 beeswaxbind.py reference --show threads
python3 beeswaxbind.py reference --show needles
python3 beeswaxbind.py reference --show wax
python3 beeswaxbind.py reference                    # all three tables
python3 beeswaxbind.py reference --search 18/3      # the thread plus the needles that fit it
python3 beeswaxbind.py reference --search zzz       # "no reference rows match", exit 0
```

The bundled data covers 12 linen thread numbers with diameter and breaking
strength in pounds and kilograms, 12 harness needle sizes with metric, US and
length, and 6 wax recipes with parts, percentages and a use note.

## 5. Machine-readable output

```bash
python3 beeswaxbind.py wax --parts 4:1 --batch 50 --json
python3 beeswaxbind.py needle --thread 18/3 --json
python3 beeswaxbind.py tension --spi 6 --json
```

```json
{
  "command": "wax",
  "ratio": "4:1",
  "preset": "standard",
  "batch_grams": 50.0,
  "beeswax_grams": 40.0,
  "beeswax_oz": 1.41,
  "rosin_grams": 10.0,
  "rosin_oz": 0.35,
  "beeswax_pct": 80,
  "rosin_pct": 20,
  "units": "both",
  "assumptions": []
}
```

In JSON mode errors are a JSON object on stderr with an `error` key, and the
process still exits 2:

```bash
python3 beeswaxbind.py tension --spi abc --json
# stderr: {"error": "spi must be a number such as 6 (got 'abc')", "field": "spi"}
```

## 6. No arguments: the wizard

On a terminal, running `beeswaxbind` with no command asks what you want to work
out and reuses the same parsers and results as the flags:

```
BeeswaxBind interactive - pick a calculator
  1  needle     recommend harness needle sizes for a thread and leather weight
  2  tension    convert stitch density and stitch length, and judge the tension
  3  wax        scale a beeswax:rosin blend to a batch weight

Choose a calculator [1-3, q to quit] (default 1): 1
Thread number [18/3]: 18/3
Leather weight in oz or mm [4oz]: 4oz
...the same recommendation block as the flag-driven command...
press Enter to run another calculation, q to quit: q
```

Invalid answers re-ask with the reason instead of exiting, and a bad answer never
ends the session. When stdin is not a terminal and there is nothing to read,
BeeswaxBind prints the command list plus a hint to run `--help` and exits 2
rather than hanging.

## Scope notes

Numbers are advisory guidance from the bundled tables, not a physics simulation:
there is no pull-force modelling, no stitch-strength prediction, no melting
temperatures or safety guidance, no supplier data, and no leather-area or
thread-consumption estimation.

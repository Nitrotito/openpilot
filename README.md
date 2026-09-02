# Tesla Model S AP1 (HW1) + magyar felület

Ez egy **személyes fork**, egyetlen autóhoz: egy Tesla Model S, első generációs Autopilot
hardverrel (AP1 / HW1, MCU1), egy **comma 4** eszközzel. A gyári openpilot és a gyári sunnypilot
ezt a hardver-generációt nem támogatja, ez az ág igen.

> **Ez vezetéstámogatás, nem önvezetés.** A kormányt nem kell fogni, az utat viszont nézni kell, és
> a felelősség végig a vezetőé. Nincs hozzá támogatás, nincs garancia, és nincs ígéret arra, hogy a
> te autódon működik.

## Mire való, és mire nem

| | |
|---|---|
| Eszköz | comma 4 (`mici`). Csak ezen épül és ezen van kipróbálva. |
| Autó | Tesla Model S, **AP1 / Hardware 1** (MCU1) |
| Éles ág | `hw1-magyar` |
| Autó-oldal | [Nitrotito/opendbc](https://github.com/Nitrotito/opendbc), `hw1` ág |

Minden más hardver-generációra (HW2, HW2.5, HW3) és minden más márkára a
[gyári sunnypilot](https://github.com/sunnypilot/sunnypilot) a jó válasz, nem ez.

## Mi van benne

- **Tesla Model S AP1 (HW1) támogatás.** A CAN-üzenetek, a kormányzás és a biztonsági határok az
  autó-oldali forkban élnek.
- **Együttműködő kormányzás** HW1-re hangolva: teljes rásegítés 1,5 Nm vezetői nyomatéktól.
- **Teljes magyar felület**, újragenerált betűatlasszal, hogy az ő és az ű is helyesen jelenjen meg.
- **Saját beállítás-panel**: sebesség-eltolás és képernyő-fényerő.
- **Képernyővédő**: pattogó Tesla-jel a sunnypilot felirat helyett.

## Telepítés

A készüléket előbb be kell kötni az autóba a comma saját útmutatója szerint. Utána a szoftver:

1. A comma 4 beállításaiban válaszd a **Custom Software** lehetőséget.
2. Add meg a telepítő címét ehhez az ághoz.
3. A készülék letölti és újraindul.

Kézzel, SSH-n keresztül is megy, ha a fenti út nem elérhető: a repót a `/data/openpilot` mappába
kell klónozni a `hw1-magyar` ágról, almodulokkal együtt, majd az updater ágát beállítani és
újraindítani.

Ha a készüléken befagy a letöltés: a git ott HTTP/2-vel elakad (mérve: fél óra, nulla bájt).
HTTP/1.1-re kell kényszeríteni. A `~/.gitconfig` az AGNOS-on nem éli túl az újraindítást, ezért a
beállítás a `/data`-ra való, és a `/data/continue.sh`-ból kell exportálni.

## Honnan van

Ez a fork nem a semmiből készült. A rétegek, alulról felfelé:

- [commaai/openpilot](https://github.com/commaai/openpilot) az alap.
- [sunnypilot/sunnypilot](https://github.com/sunnypilot/sunnypilot) az a közösségi fork, amire ez
  épül, és amiből a funkciók nagy része jön.
- [xnor-tech/openpilot](https://github.com/xnor-tech/openpilot) és
  [xnor-tech/opendbc](https://github.com/xnor-tech/opendbc): a régi Tesla-hardver támogatásának
  forrása.
- [P6g9YHK6/SunnyPilot-TeslaHW1](https://github.com/P6g9YHK6/SunnyPilot-TeslaHW1): az a fork, ami a
  kettőt először összehozta, és amiből a HW1-es munka nálunk indult.

A magyarítás, a beállítás-panel, a képernyővédő és a HW1-re hangolt együttműködő kormányzás a mi
munkánk. Minden más a fenti projekteké, a saját licenceik szerint.

---

# Tesla Model S AP1 (HW1) with a Hungarian UI

A **personal fork**, maintained for a single car: a Tesla Model S with first generation Autopilot
hardware (AP1 / HW1, MCU1) and a **comma 4** device. Neither stock openpilot nor stock sunnypilot
supports this hardware generation. This branch does.

> **This is driver assistance, not self driving.** You do not have to hold the wheel, but you do
> have to watch the road, and the driver stays responsible at all times. No support, no warranty,
> and no promise that it works on your car.

## What it is for, and what it is not

| | |
|---|---|
| Device | comma 4 (`mici`), the only unit this is built and tested on |
| Car | Tesla Model S, **AP1 / Hardware 1** (MCU1) |
| Live branch | `hw1-magyar` |
| Car side | [Nitrotito/opendbc](https://github.com/Nitrotito/opendbc), branch `hw1` |

For any other hardware generation (HW2, HW2.5, HW3) or any other make,
[stock sunnypilot](https://github.com/sunnypilot/sunnypilot) is the right answer, not this.

## What is in it

- **Tesla Model S AP1 (HW1) support.** The CAN messages, the steering and the safety limits live in
  the car-side fork.
- **Cooperative steering** tuned for HW1: full assist from 1.5 Nm of driver torque.
- **A full Hungarian UI**, with a regenerated font atlas so the double-acute letters render.
- **An extra settings panel**: speed offset and screen brightness.
- **Screensaver**: a bouncing Tesla mark instead of the sunnypilot wordmark.

## Installing

Wire the device into the car first, following comma's own guide. Then the software:

1. In the comma 4 settings, pick **Custom Software**.
2. Enter the installer address for this branch.
3. The device downloads it and reboots.

It can also be done by hand over SSH: clone the repository into `/data/openpilot` from the
`hw1-magyar` branch with submodules, point the updater at that branch, and reboot.

If a download stalls on the device: git over HTTP/2 hangs there (measured: half an hour, zero
bytes). Force HTTP/1.1. `~/.gitconfig` does not survive a reboot on AGNOS, so the setting belongs
on `/data` and has to be exported from `/data/continue.sh`.

## Where this comes from

This fork was not written from scratch. The layers, bottom up:

- [commaai/openpilot](https://github.com/commaai/openpilot) is the base.
- [sunnypilot/sunnypilot](https://github.com/sunnypilot/sunnypilot) is the community fork this is
  built on, and where most of the features come from.
- [xnor-tech/openpilot](https://github.com/xnor-tech/openpilot) and
  [xnor-tech/opendbc](https://github.com/xnor-tech/opendbc): the source of support for the older
  Tesla hardware.
- [P6g9YHK6/SunnyPilot-TeslaHW1](https://github.com/P6g9YHK6/SunnyPilot-TeslaHW1): the fork that
  first brought the two together, and where our HW1 work started.

The Hungarian translation, the settings panel, the screensaver and the HW1 cooperative steering
tuning are ours. Everything else belongs to the projects above, under their own licences.

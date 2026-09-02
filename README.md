# Nitrotito fork: Tesla Model S (AP1 / HW1) + Hungarian UI

**This is not stock sunnypilot.** It is a personal fork, maintained for a single car.
Live branch: `hw1-magyar`. This is the one the device actually runs.
The car-side changes live in a second fork: [Nitrotito/opendbc](https://github.com/Nitrotito/opendbc/tree/hw1), branch `hw1`.

What this fork adds on top of sunnypilot:

- **Tesla Model S with AP1 (HW1)**, based on the xnor-tech port. Neither stock openpilot nor
  stock sunnypilot supports this hardware generation.
- **Hungarian UI translation**, with a regenerated font atlas so that ő and ű render correctly.
- **An extra settings panel** in the UI: speed offset and screen brightness.
- **Screensaver**: a bouncing Tesla mark instead of the sunnypilot wordmark. The licence plate
  under it is read from `/data/license_plate` on the device, and is deliberately never committed.

No support, no warranty, and no promise that it works on your car. This is driver assistance
software: the driver stays responsible at all times.

---

# Nitrotito fork: Tesla Model S (AP1 / HW1) és magyar felület

**Ez nem a gyári sunnypilot.** Személyes fork, egyetlen autóhoz karbantartva.
Az éles ág: `hw1-magyar`. A készülék ezt futtatja.
Az autó-oldali változtatások külön forkban élnek: [Nitrotito/opendbc](https://github.com/Nitrotito/opendbc/tree/hw1), `hw1` ág.

Amit ez a fork hozzátesz a sunnypilothoz:

- **Tesla Model S AP1 (HW1) támogatás**, az xnor-tech port alapján. Ezt a hardver-generációt sem
  a gyári openpilot, sem a gyári sunnypilot nem ismeri.
- **Teljes magyar felület**, újragenerált betűatlasszal, hogy az ő és az ű is helyesen jelenjen meg.
- **Egy saját beállítás-panel** a felületen: sebesség-eltolás és képernyő-fényerő.
- **Képernyővédő**: pattogó Tesla-jel a sunnypilot felirat helyett. Az alatta lévő rendszámot a
  készülék `/data/license_plate` fájljából olvassa, és szándékosan sosem kerül be a kódba.

Nincs hozzá támogatás, nincs garancia, és nincs ígéret arra, hogy a te autódon működik. Ez
vezetéstámogató szoftver: a felelősség végig a vezetőé.

---

## Supported hardware / Támogatott eszköz

| | |
|---|---|
| Device | comma 4 (`mici`), the only unit this fork is built and tested on |
| Car | Tesla Model S with **AP1 / Hardware 1** (MCU1) |
| Base | sunnypilot, which is itself a fork of comma.ai's openpilot |
| Car support | [Nitrotito/opendbc](https://github.com/Nitrotito/opendbc), branch `hw1` |

Anything else (HW2, HW2.5, HW3, other makes) is out of scope here. Stock sunnypilot supports
those far better than this branch does.

Eszköz: comma 4 (`mici`), csak ezen épül és ezen van kipróbálva. Autó: Tesla Model S **AP1 /
Hardware 1** (MCU1). Minden más hardver-generációra és márkára a gyári sunnypilot a jó válasz,
nem ez az ág.

## Installation / Telepítés

**This fork is not installable from the comma installer URL.** It is set up by hand, because the
device has to end up on this branch with the submodules pinned to our commits:

1. SSH into the device.
2. Clone this repository into `/data/openpilot`, branch `hw1-magyar`, with submodules:
   `git clone --recurse-submodules -b hw1-magyar https://github.com/Nitrotito/sunnypilot.git /data/openpilot`
3. Tell the updater which branch to follow:
   `echo -n "hw1-magyar" > /data/params/d/UpdaterTargetBranch`
4. Optional: put the licence plate shown on the screensaver into `/data/license_plate`.
   Leave the file out and the screensaver simply shows the mark.
5. Reboot.

Note for anyone hitting a stalled `git fetch` on the device: git over HTTP/2 stalls there
(measured: half an hour, zero bytes). Force HTTP/1.1. `~/.gitconfig` does not survive a reboot on
AGNOS, so the setting belongs on `/data` and has to be exported from `/data/continue.sh`.

**Ez a fork a comma telepítő URL-jéről nem telepíthető.** Kézzel kell felrakni, mert a készüléknek
erre az ágra kell kerülnie, az almodulokkal együtt:

1. SSH a készülékre.
2. A repó klónozása a `/data/openpilot` mappába, `hw1-magyar` ágról, almodulokkal.
3. Az updater ágának beállítása: `UpdaterTargetBranch` értéke `hw1-magyar`.
4. Nem kötelező: a képernyővédőn megjelenő rendszám a `/data/license_plate` fájlba. Ha nincs ilyen
   fájl, a képernyővédő csak a jelet mutatja.
5. Újraindítás.

Ha a készüléken befagy a letöltés: a git HTTP/2-vel ott elakad (mérve: fél óra, nulla bájt).
HTTP/1.1-re kell kényszeríteni. A `~/.gitconfig` az AGNOS-on nem éli túl az újraindítást, ezért a
beállítás a `/data`-ra való, és a `/data/continue.sh`-ból kell exportálni.

---

![](https://user-images.githubusercontent.com/47793918/233812617-beab2e71-57b9-479e-8bff-c3931347ca40.png)

## 🌞 What is sunnypilot?
[sunnypilot](https://github.com/sunnyhaibin/sunnypilot) is a fork of comma.ai's openpilot, an open source driver assistance system. sunnypilot offers the user a unique driving experience for over 300+ supported car makes and models with modified behaviors of driving assist engagements. sunnypilot complies with comma.ai's safety rules as accurately as possible.

## 💭 Join our Community Forum
Join the official sunnypilot community forum to stay up to date with all the latest features and be a part of shaping the future of sunnypilot!
* https://community.sunnypilot.ai/

## Documentation
https://docs.sunnypilot.ai/ is your one stop shop for everything from features to installation to FAQ about the sunnypilot

## 🚘 Running on a dedicated device in a car
First, check out this list of items you'll need to [get started](https://community.sunnypilot.ai/t/getting-started-using-sunnypilot-in-your-supported-car/251).

## Installation
Next, refer to the sunnypilot community forum for [installation instructions](https://community.sunnypilot.ai/t/read-before-installing-sunnypilot/254), as well as a complete list of [Recommended Branch Installations](https://community.sunnypilot.ai/t/recommended-branch-installations/235).

## 🎆 Pull Requests
We welcome both pull requests and issues on GitHub. Bug fixes are encouraged.

Pull requests should be against the most current `master` branch.

## 📊 User Data

By default, sunnypilot uploads the driving data to comma servers. You can also access your data through [comma connect](https://connect.comma.ai/).

sunnypilot is open source software. The user is free to disable data collection if they wish to do so.

sunnypilot logs the road-facing camera, CAN, GPS, IMU, magnetometer, thermal sensors, crashes, and operating system logs.
The driver-facing camera and microphone are only logged if you explicitly opt-in in settings.

By using this software, you understand that use of this software or its related services will generate certain types of user data, which may be logged and stored at the sole discretion of comma. By accepting this agreement, you grant an irrevocable, perpetual, worldwide right to comma for the use of this data.

## Licensing

sunnypilot is released under the [MIT License](LICENSE). This repository includes original work as well as significant portions of code derived from [openpilot by comma.ai](https://github.com/commaai/openpilot), which is also released under the MIT license with additional disclaimers.

The original openpilot license notice, including comma.ai’s indemnification and alpha software disclaimer, is reproduced below as required:

> openpilot is released under the MIT license. Some parts of the software are released under other licenses as specified.
>
> Any user of this software shall indemnify and hold harmless Comma.ai, Inc. and its directors, officers, employees, agents, stockholders, affiliates, subcontractors and customers from and against all allegations, claims, actions, suits, demands, damages, liabilities, obligations, losses, settlements, judgments, costs and expenses (including without limitation attorneys’ fees and costs) which arise out of, relate to or result from any use of this software by user.
>
> **THIS IS ALPHA QUALITY SOFTWARE FOR RESEARCH PURPOSES ONLY. THIS IS NOT A PRODUCT.
> YOU ARE RESPONSIBLE FOR COMPLYING WITH LOCAL LAWS AND REGULATIONS.
> NO WARRANTY EXPRESSED OR IMPLIED.**

For full license terms, please see the [`LICENSE`](LICENSE) file.

## 💰 Support sunnypilot
If you find any of the features useful, consider becoming a [sponsor on GitHub](https://github.com/sponsors/sunnyhaibin) to support future feature development and improvements.


By becoming a sponsor, you will gain access to exclusive content, early access to new features, and the opportunity to directly influence the project's development.


<h3>GitHub Sponsor</h3>

<a href="https://github.com/sponsors/sunnyhaibin">
  <img src="https://user-images.githubusercontent.com/47793918/244135584-9800acbd-69fd-4b2b-bec9-e5fa2d85c817.png" alt="Become a Sponsor" width="300" style="max-width: 100%; height: auto;">
</a>
<br>

<h3>PayPal</h3>

<a href="https://paypal.me/sunnyhaibin0850" target="_blank">
<img src="https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif" alt="PayPal this" title="PayPal - The safer, easier way to pay online!" border="0" />
</a>
<br></br>

Your continuous love and support are greatly appreciated! Enjoy 🥰

<span>-</span> Jason, Founder of sunnypilot

# Sepehr Baba: context, sources and verification limits

Research date: **2026-09-25**. This is an attributed research record, not an
independent forensic authentication or a legal finding.

## Purpose

Preserve the recording known as **“Sepehr Baba”** and reconstruct the environment
it records so that the aftermath of the January 8–9, 2026 killings in Iran can
be studied and documented for future accountability. The project owner describes
the recording as filmed by a parent among victims' bodies. This purpose requires
preserving uncertainty as carefully as preserving visible detail.

## Publication history and subsequent reporting

Dates below distinguish publication from the event being reported. They are
not a verified filming date. Translations and summaries are this project's;
we have not interviewed the family or identified anyone by face or voice.

| Date | Report or observation | Source and limit |
| --- | --- | --- |
| January 14, 2026 | Amnesty documented unlawful killings by security forces, the internet shutdown, and families searching for relatives at Kahrizak. | [Amnesty International](https://www.amnesty.org/en/latest/news/2026/01/iran-massacre-of-protesters-demands-global-diplomatic-action-to-signal-an-end-to-impunity/). Context from an earlier investigation of other footage, not authentication of our file. |
| January 23 | Vahid Online's post carries this publication date; its current caption identifies Sepehr Shokri's father. | [Post 70115](https://t.me/VahidOnline/70115). Inspected directly as described below; the post has been edited. |
| January 24 | Persian-language coverage described the father's phone recording and repeated search for Sepehr. | [Iran International analysis](https://www.iranintl.com/202601246520). Early coverage, not a forensic report. |
| January 25, according to the publisher's relative dating | The post says identifying audio was restored two days after first publication, following a state-TV attribution to another family. | [Publisher's updated caption](https://t.me/VahidOnline/70115). The update date is inferred from its wording; no independently retained January revision is available here. |
| January 26–27 | Coverage distinguished Sepehr Shokri from Sepehr Ebrahimi and described the audio restoration. | [Ayandegan, January 26](https://ayandegan.news/posts/930971), updated August 20; [Iran International, January 27](https://www.iranintl.com/en/202601260391). The latter said its efforts to contact the family had not succeeded at that time. |
| February 4 | Iran International reported messages about families naming newborns Sepehr after the video circulated. | [Iran International](https://www.iranintl.com/202602044507). Attributed reader accounts, not a population-wide measure. |
| February 17, reported February 18 | His father urged mourners to celebrate life and joy. | [Al Jazeera](https://www.aljazeera.com/news/2026/2/18/iranian-families-mark-protest-killings-as-schools-observe-strikes). Memorial reporting. |
| March 21 | HRANA identified the father as Esmail Shokri and reported a violent arrest at his son's grave in Behesht-e Zahra. | [HRANA arrest report](https://www.hra-news.org/2026/hranews/a-08f7f295/), citing a source close to the family. |
| March 21 evening, reported March 22 | HRANA reported his release after approximately five hours; charges and release conditions were not established. | [HRANA follow-up](https://www.hra-news.org/2026/hranews/a-1c83b463/). Do not describe him as still detained on the basis of the earlier report. |
| September 9 | IranWire reported Sepehr's mother's participation in a candle-lighting remembrance campaign at his grave. | [IranWire](https://iranwire.com/en/news/157387-today-in-the-iranian-cybersphere-september-9-2026/). Later family reporting, not proof of the father's present circumstances. |

### Who filmed it, and why the video matters

Public reporting attributes the recording to Sepehr Shokri's father, subsequently
named Esmail (also transliterated Ismail) Shokri, **اسماعیل شکری**. Vahid Online
is the publisher credited in the publication trail, not the person this project
claims held the camera. Iran International's January 27 account describes the
search and says the video does not show whether he finds his son.
[Video account](https://www.iranintl.com/en/202601260391) ·
[Father's name](https://www.hra-news.org/2026/hranews/a-08f7f295/)

The father's repeated call became a public expression of bereavement and a
search for accountability. Reporting months later connected it to the family's
continuing remembrance. For this project, the recording's value also lies in
preserving an extended view of the physical setting and the relationships
between visible spaces. That is our reason for attempting reconstruction, not
a claim that a 3D model can establish what happened outside the camera's view.
[Early reception](https://www.iranintl.com/202601246520) ·
[Later remembrance](https://iranwire.com/en/news/157387-today-in-the-iranian-cybersphere-september-9-2026/)

The reported attempt to associate the recording with Sepehr Ebrahimi's family
makes careful attribution especially important. We keep the families distinct
and preserve the acquired audio unchanged. We do not derive identities, victim
counts, or individual responsibility from reconstruction geometry.
[Reporting on the attribution dispute](https://ayandegan.news/posts/930971)

### Direct publication-link check on September 25, 2026

We fetched the [Telegram post's embed](https://t.me/VahidOnline/70115?embed=1&mode=tme)
and inspected its timestamp, caption, and links. It contains:

- A machine-readable post timestamp of `2026-01-23T04:08:30+00:00`.
- An initial [X post link](https://x.com/Vahid/status/2014549138189254811) and
  an [updated X post link](https://x.com/Vahid/status/2015559558437990439).
- A `twimg` download link exactly equal to the user-supplied source URL below.

This narrows a previously unresolved provenance question: the acquired URL is
linked by the publisher's current post. It does **not** independently establish
first publication, the earlier post's bytes, the camera original, or complete
custody. We inspected the Telegram page; the linked X posts' contents were not
independently retrieved. No historical post snapshot is held by this repository.

### Conflicting details and remaining uncertainty

Reports differ on some biographical details: Al Jazeera gives age 19; Iran
International gives 25. The README therefore omits an age. Neither publication
dates nor the post's update date establish when the recording was filmed.
The publisher describes restoring audio, but we have not compared both published
versions frame by frame or established any edits preceding publication.
[Al Jazeera](https://www.aljazeera.com/news/2026/2/18/iranian-families-mark-protest-killings-as-schools-observe-strikes) ·
[Iran International](https://www.iranintl.com/en/202601260391)

## What we verified about the acquired file

The exact URL was supplied by the project owner:

```text
https://video.twimg.com/amplify_video/2015558220249530368/vid/avc1/1080x1920/2LxgD15qCvFD42mt.mp4?tag=21
```

The retained file was first documented locally on September 22, 2026, with the
same SHA-256 now recorded in [the archival manifest](../evidence/source/provenance.json).
On September 25 its checksum was verified before adding the unchanged copy to
Git LFS. It is 417,094,424 bytes; the container duration is 737.301333 seconds,
with 1080 × 1920 H.264 video, 12,793 video frames and an AAC audio stream.
Variable frame timing must be preserved in the frame-to-video mapping.

The supplied URL is an X/Twitter media-CDN URL. It does not itself establish
the identity of the uploader, recorder, people shown, or the capture date.
The project has not acquired the original phone file, recorder testimony,
original upload response headers, or a complete pre-download custody history.
The archival record is retrospective where indicated; missing acquisition
details are not invented from file modification times.

## Verification work still open

1. Extend the verified URL-to-post connection into a version history: obtain
   earlier published copies and compare frames, audio, and hashes. Establish
   first publication independently; the current edited post alone cannot do so.
2. Obtain the camera-original file and a documented transfer history if it
   becomes available through an authorized source. Retain this platform copy
   under its existing identifier regardless.
3. Independently corroborate location and capture date using attributable
   reference material. Record evidence for each claim separately.
4. Have source-language transcription and translation reviewed, retaining
   timecodes, inaudible segments and uncertainty. No verified transcript is
   currently supplied by this repository.
5. Validate reconstructed geometry against source views and external scale
   references before making any measurement or scene-layout claim.

The [Berkeley Protocol](https://digitallibrary.un.org/record/3973652?ln=en)
is a relevant preservation and verification reference. Our current pilot remains
an experimental derived visualization, not a certified forensic reconstruction
or a guarantee that a court will accept any particular item.

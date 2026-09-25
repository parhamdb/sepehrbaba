# Sepehr Baba: context, sources and verification limits

Research date: **2026-09-25**. This is an attributed research record, not an
independent forensic authentication or a legal finding.

## Purpose

Preserve the recording known as **“Sepehr Baba”** and reconstruct the environment
it records so that the aftermath of the January 8–9, 2026 killings in Iran can
be studied and documented for future accountability. The project owner describes
the recording as filmed by a parent among victims' bodies. This purpose requires
preserving uncertainty as carefully as preserving visible detail.

## What the public sources establish

| Source | Reported finding | What it does not establish for this repository |
| --- | --- | --- |
| [Iran International, January 24, 2026: “12 minutes in Kahrizak; Sepehr Baba … where are you?”](https://www.iranintl.com/202601246520) | Describes a twelve-minute Kahrizak Legal Medicine recording of a father searching among bodies and calling for Sepehr. | No published hash comparison with our MP4; this article is labeled analysis, not a forensic authentication report. |
| [Iran International, February 4, 2026](https://www.iranintl.com/202602044507) | Identifies the father in the widely circulated recording as Sepehr Shokri's father. | We have not identified anyone from facial or voice recognition, or independently verified that attribution against this file. |
| [Ayandegan, January 26, 2026; page updated later](https://ayandegan.news/posts/930971) | Attributes a later version to Vahid Online and reports that a few seconds of identifying audio had been removed from an earlier version. | We have not established which publication/version the supplied CDN URL belongs to, or verified its complete edit history. |
| [Amnesty International, January 14, 2026](https://www.amnesty.org/en/latest/news/2026/01/iran-massacre-of-protesters-demands-global-diplomatic-action-to-signal-an-end-to-impunity/) | Reports mass unlawful killings by Iranian security forces after January 8 and analyzes Kahrizak footage showing families searching among bodies. | Its earlier investigation must not be presented as authentication of this specific twelve-minute file. |

These sources support the reported historical setting. Publication dates are
not filming dates. Reports about different recordings from the same facility
must not be combined into a claimed verification of this recording. In
particular, avoid conflating reported Sepehr Shokri and Sepehr Ebrahimi identities.

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

1. Link this exact file to its originating public post and known published
   versions, using frame/audio comparisons and hashes where possible.
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

<!--
SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later
-->

<div id="top"></div>

<p align="center">
  <a href="https://github.com/ikajdan/steammetadatatool/actions/workflows/ci.yaml">
  <img alt="Build" src="https://img.shields.io/github/actions/workflow/status/ikajdan/steammetadatatool/ci.yaml?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGhlaWdodD0iNDhweCIgdmlld0JveD0iMCAtOTYwIDk2MCA5NjAiIHdpZHRoPSI0OHB4IiBmaWxsPSIjZmZmZmZmIj48cGF0aCBkPSJNMzQzLTM1NHEtMTA2LjI1IDAtMTgwLjEyLTczLjk2UTg5LTUwMS45MiA4OS02MDdxMC0yMSA0LTM3LjV0MTAtMzcuNXE0LTguNSAxMS41LTE1dDE3LjUtOC41cTcuNzUtMS41IDE2LjkzLjQ4IDkuMTggMS45NyAxOC4yMSAxMC4xNkwyNzQtNTg3bDk0LTg4LTExMi44Ni0xMTIuODZxLTYuOTctOC4xLTEwLjA1LTE3LjE5LTMuMDktOS4wOS0uNTktMTcuNzkgMS42OC04LjMxIDguMTQtMTUuNzYgNi40Ni03LjQ1IDE2LjcxLTEyLjA1UTI4OC04NTYgMzA1LTg2MXQzNy44NS01cTEwOC44OSAwIDE4My41MiA3NS41NFE2MDEtNzE0LjkyIDYwMS02MDdxMCAyMy4yLTMgNDQuNzctMyAyMS41Ni0xMiA0My4yM2wyMzcgMjM1cTMyIDMzLjk1IDMxIDc5LjM4LTEgNDUuNDQtMzQuMjggNzYuNjItMzEuMjMgMzItNzUuNDggMzFRNzAwLTk4IDY2OC0xMzBMNDMwLTM2OXEtMjEgOS00MC44MiAxMlQzNDMtMzU0Wm0uNi04MHEyNC40IDAgNTIuMTktOFQ0NDUtNDY2bDI4MSAyODBxNyAxMCAxOS4yNSA5LjgzIDEyLjI1LS4xOCAyMS43NS05LjQyIDctOC40MSA3LTE5Ljc3IDAtMTEuMzctNy0yMS42NEw0OTAtNTAzcTE2LTIyIDI0LTQ5LjV0OC01NC41cTAtNzUuNjItNTYuNS0xMjguMzFUMzM4LTc4OWw5MSA5NHExMyAxMy42NCAxMi41IDMzLjQxUTQ0MS02NDEuODIgNDI4LTYyOEwzMTktNTI4cS0xNS4zNiAxNS0zNC42NCAxNS0xOS4yNyAwLTMxLjM2LTE1bC04OC04NnEzIDc5IDU1LjY3IDEyOS41VDM0My42LTQzNFpNNDcxLTQ4MloiLz48L3N2Zz4=">
  </a>
  <a href="https://github.com/ikajdan/steammetadatatool/releases">
  <img alt="Release" src="https://img.shields.io/github/v/release/ikajdan/steammetadatatool?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGhlaWdodD0iNDhweCIgdmlld0JveD0iMCAtOTYwIDk2MCA5NjAiIHdpZHRoPSI0OHB4IiBmaWxsPSIjZmZmZmZmIj48cGF0aCBkPSJtNDM3LTQzOS02OS03M3EtMTAuMjUtMTItMjUuMTItMTEuNVEzMjgtNTIzIDMxNy01MTRxLTEyIDEyLjUxLTEyIDI3LjI2UTMwNS00NzIgMzE3LTQ2MWw4OCA4NnExMi4zNiAxNSAzMi4xOCAxNVQ0NzAtMzc1bDE3NC0xNzJxMTAtOSAxMC0yNC41VDY0My01OThxLTExLTgtMjUtOHQtMjMgMTBMNDM3LTQzOVpNMzE2LTY4bC02MC0xMDMtMTE5LTI1cS0xOS0zLTI5LjUtMTcuMTNROTctMjI3LjI1IDEwMC0yNDVsMTQtMTE1LjdMMzgtNDUxcS0xMC0xMi4zOS0xMC0yOS4yUTI4LTQ5NyAzOC01MTBsNzYtODguM0wxMDAtNzE0cS0zLTE3Ljc1IDcuNS0zMS44OFExMTgtNzYwIDEzNy03NjRsMTE5LjMxLTI0LjJMMzE2LTg5MnE4Ljg4LTE0LjU2IDI1LjkyLTIwLjI4UTM1OC45Ni05MTggMzc2LTkxMWwxMDQgNDkgMTA1LTQ5cTE2LTUgMzMuMDYtLjgyUTYzNS4xMS05MDcuNjQgNjQ0LTg5M2w2MC42OSAxMDQuOEw4MjMtNzY0cTE5IDQgMjkuNSAxOC4xMlE4NjMtNzMxLjc1IDg2MC03MTRsLTE0IDExNS43IDc2IDg4LjNxMTAgMTMuMzkgMTAgMzAuMiAwIDE2LjgtMTAgMjguOGwtNzYgOTAuM0w4NjAtMjQ1cTMgMTcuNzUtNy41IDMxLjg3UTg0Mi0xOTkgODIzLTE5NmwtMTE4IDI1LTYxIDEwNHEtOC44OSAxNC42NC0yNS45NCAxOC44MlE2MDEtNDQgNTg1LTQ5TDQ4MC05OCAzNzYtNDlxLTE3IDUtMzQuMDYuMzJRMzI0Ljg5LTUzLjM2IDMxNi02OFptNjAuNzQtODMgMTAzLjEyLTQzLjU2TDU4Ni0xNTFsNjUtOTYgMTEyLTI5LTExLTExNi4xOSA3Ny04Ny45TDc1Mi01NzBsMTEtMTE2LTExMi0yNy02Ni42Ni05Ni0xMDQuMTYgNDMuNDZMMzc0LTgwOWwtNjQuNzIgOTYuMjRMMTk4LTY4Ni40NSAyMDgtNTcwbC03NyA5MCA3NyA4OC0xMCAxMTguNDYgMTExLjEgMjYuMzFMMzc2Ljc0LTE1MVpNNDgwLTQ4MFoiLz48L3N2Zz4=" />
  </a>
  <a href="#license">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9Ii0wLjA5OTkyODEgLTAuMDk5NDAyIDE2LjIgMTQuNyI+Cgk8cGF0aCBkPSJNOC43NS43NVYyaC45ODVjLjMwNCAwIC42MDMuMDguODY3LjIzMWwxLjI5LjczNmMuMDM4LjAyMi4wOC4wMzMuMTI0LjAzM2gyLjIzNGEuNzUuNzUgMCAwIDEgMCAxLjVoLS40MjdsMi4xMTEgNC42OTJhLjc1Ljc1IDAgMCAxLS4xNTQuODM4bC0uNTMtLjUzLjUyOS41MzEtLjAwMS4wMDItLjAwMi4wMDItLjAwNi4wMDYtLjAwNi4wMDUtLjAxLjAxLS4wNDUuMDRjLS4yMS4xNzYtLjQ0MS4zMjctLjY4Ni40NUMxNC41NTYgMTAuNzggMTMuODggMTEgMTMgMTFhNC40OTggNC40OTggMCAwIDEtMi4wMjMtLjQ1NCAzLjU0NCAzLjU0NCAwIDAgMS0uNjg2LS40NWwtLjA0NS0uMDQtLjAxNi0uMDE1LS4wMDYtLjAwNi0uMDA0LS4wMDR2LS4wMDFhLjc1Ljc1IDAgMCAxLS4xNTQtLjgzOEwxMi4xNzggNC41aC0uMTYyYy0uMzA1IDAtLjYwNC0uMDc5LS44NjgtLjIzMWwtMS4yOS0uNzM2YS4yNDUuMjQ1IDAgMCAwLS4xMjQtLjAzM0g4Ljc1VjEzaDIuNWEuNzUuNzUgMCAwIDEgMCAxLjVoLTYuNWEuNzUuNzUgMCAwIDEgMC0xLjVoMi41VjMuNWgtLjk4NGEuMjQ1LjI0NSAwIDAgMC0uMTI0LjAzM2wtMS4yODkuNzM3Yy0uMjY1LjE1LS41NjQuMjMtLjg2OS4yM2gtLjE2MmwyLjExMiA0LjY5MmEuNzUuNzUgMCAwIDEtLjE1NC44MzhsLS41My0uNTMuNTI5LjUzMS0uMDAxLjAwMi0uMDAyLjAwMi0uMDA2LjAwNi0uMDE2LjAxNS0uMDQ1LjA0Yy0uMjEuMTc2LS40NDEuMzI3LS42ODYuNDVDNC41NTYgMTAuNzggMy44OCAxMSAzIDExYTQuNDk4IDQuNDk4IDAgMCAxLTIuMDIzLS40NTQgMy41NDQgMy41NDQgMCAwIDEtLjY4Ni0uNDVsLS4wNDUtLjA0LS4wMTYtLjAxNS0uMDA2LS4wMDYtLjAwNC0uMDA0di0uMDAxYS43NS43NSAwIDAgMS0uMTU0LS44MzhMMi4xNzggNC41SDEuNzVhLjc1Ljc1IDAgMCAxIDAtMS41aDIuMjM0YS4yNDkuMjQ5IDAgMCAwIC4xMjUtLjAzM2wxLjI4OC0uNzM3Yy4yNjUtLjE1LjU2NC0uMjMuODY5LS4yM2guOTg0Vi43NWEuNzUuNzUgMCAwIDEgMS41IDBabTIuOTQ1IDguNDc3Yy4yODUuMTM1LjcxOC4yNzMgMS4zMDUuMjczczEuMDItLjEzOCAxLjMwNS0uMjczTDEzIDYuMzI3Wm0tMTAgMGMuMjg1LjEzNS43MTguMjczIDEuMzA1LjI3M3MxLjAyLS4xMzggMS4zMDUtLjI3M0wzIDYuMzI3WiIgZmlsbD0iI2ZmZmZmZiIvPgo8L3N2Zz4=" />
  </a>
  <a href="https://github.com/ikajdan/steammetadatatool/releases">
  <img alt="Downloads" src="https://img.shields.io/github/downloads/ikajdan/steammetadatatool/total?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iNDhweCIgaGVpZ2h0PSI0OHB4IiBmaWxsPSIjZmZmZmZmIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgLTk2MCA5NjAgOTYwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZD0ibTQ4MC4yMy0zMjUuNTZxLTkuMzk3MSAwLTE5Ljk2OS00LjIxNzUtMTAuNTcyLTQuMjI4Ny0xNy4yMzktMTEuNDQ0bC0xNzcuODctMTc4Ljk5cS0xNS42NjItMTMuODI3LTE1LjMzNy0zNC45MTUgMC4zMjQ0Mi0yMS4wNzYgMTYuMDItMzYuMjAxIDE0LjMwOC0xNS4xOTIgMzYuMjM1LTE0LjU1NCAyMS45MjcgMC42NDg4NSAzNi45MTcgMTUuMTkybDkwLjYxNSA5MC42MTV2LTMxMXEwLTIxLjk4MyAxNC4zODctMzYuNzI3IDE0LjM4Ny0xNC43MzMgMzYuMzU4LTE0LjczM3QzNi41MTUgMTQuNzMzcTE0LjU0MyAxNC43NDUgMTQuNTQzIDM2LjcyN3YzMTFsOTEuNzM0LTkwLjYxNXExNC4xNzQtMTQuNTQzIDM0LjQtMTUuMjgyIDIwLjIyNi0wLjcyNzE2IDM2LjI1NyAxNC4wNzMgMTQuMzY0IDE0LjYzMyAxNC4zNjQgMzYuMjQ2IDAgMjEuNjEzLTE0LjU0MyAzNy42NzhsLTE3Ni43NiAxNzYuNzZxLTYuNDk5NyA3LjIxNTctMTcuMDI3IDExLjQ0NC0xMC41MjcgNC4yMTc1LTE5LjYgNC4yMTc1em0tMjc5Ljk3IDIyNy4xcS00MS41OTQgMC03MS42OTgtMzAuMTA0LTMwLjEwNC0zMC4xMDQtMzAuMTA0LTcxLjY5OHYtMTA5LjYzcTAtMjAuNTYyIDE0LjM4Ny0zNS40NTIgMTQuMzg3LTE0Ljg5IDM2LjM1OC0xNC44OXQzNi41MTUgMTQuODlxMTQuNTQzIDE0Ljg5IDE0LjU0MyAzNS40NTJ2MTA5LjYzaDU1OS4zNXYtMTA5LjYzcTAtMjAuNTYyIDE1LjE3LTM1LjQ1MiAxNS4xNy0xNC44OSAzNi4wMzQtMTQuODkgMjIuNDMgMCAzNy4wNzQgMTQuODkgMTQuNjQ0IDE0Ljg5IDE0LjY0NCAzNS40NTJ2MTA5LjYzcTAgNDEuNTk0LTMwLjQ0IDcxLjY5OC0zMC40MjkgMzAuMTA0LTcyLjQ4MSAzMC4xMDR6IiBzdHJva2Utd2lkdGg9IjEuMTE4NyIvPgo8L3N2Zz4K" />
  </a>
  <img alt="GitHub Stars" src="https://img.shields.io/github/stars/ikajdan/steammetadatatool?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZlcnNpb249IjEuMSIgdmlld0JveD0iMCAwIDE2IDE2IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZD0iTTggLjI1YS43NS43NSAwIDAgMSAuNjczLjQxOGwxLjg4MiAzLjgxNSA0LjIxLjYxMmEuNzUuNzUgMCAwIDEgLjQxNiAxLjI3OWwtMy4wNDYgMi45Ny43MTkgNC4xOTJhLjc1MS43NTEgMCAwIDEtMS4wODguNzkxTDggMTIuMzQ3bC0zLjc2NiAxLjk4YS43NS43NSAwIDAgMS0xLjA4OC0uNzlsLjcyLTQuMTk0TC44MTggNi4zNzRhLjc1Ljc1IDAgMCAxIC40MTYtMS4yOGw0LjIxLS42MTFMNy4zMjcuNjY4QS43NS43NSAwIDAgMSA4IC4yNVptMCAyLjQ0NUw2LjYxNSA1LjVhLjc1Ljc1IDAgMCAxLS41NjQuNDFsLTMuMDk3LjQ1IDIuMjQgMi4xODRhLjc1Ljc1IDAgMCAxIC4yMTYuNjY0bC0uNTI4IDMuMDg0IDIuNzY5LTEuNDU2YS43NS43NSAwIDAgMSAuNjk4IDBsMi43NyAxLjQ1Ni0uNTMtMy4wODRhLjc1Ljc1IDAgMCAxIC4yMTYtLjY2NGwyLjI0LTIuMTgzLTMuMDk2LS40NWEuNzUuNzUgMCAwIDEtLjU2NC0uNDFMOCAyLjY5NFoiIGZpbGw9IiNmZmYiLz4KPC9zdmc+Cg==" />
  <img alt="GitHub Forks" src="https://img.shields.io/github/forks/ikajdan/steammetadatatool?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZlcnNpb249IjEuMSIgdmlld0JveD0iMCAwIDE2IDE2IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZD0iTTUgNS4zNzJ2Ljg3OGMwIC40MTQuMzM2Ljc1Ljc1Ljc1aDQuNWEuNzUuNzUgMCAwIDAgLjc1LS43NXYtLjg3OGEyLjI1IDIuMjUgMCAxIDEgMS41IDB2Ljg3OGEyLjI1IDIuMjUgMCAwIDEtMi4yNSAyLjI1aC0xLjV2Mi4xMjhhMi4yNTEgMi4yNTEgMCAxIDEtMS41IDBWOC41aC0xLjVBMi4yNSAyLjI1IDAgMCAxIDMuNSA2LjI1di0uODc4YTIuMjUgMi4yNSAwIDEgMSAxLjUgMFpNNSAzLjI1YS43NS43NSAwIDEgMC0xLjUgMCAuNzUuNzUgMCAwIDAgMS41IDBabTYuNzUuNzVhLjc1Ljc1IDAgMSAwIDAtMS41Ljc1Ljc1IDAgMCAwIDAgMS41Wm0tMyA4Ljc1YS43NS43NSAwIDEgMC0xLjUgMCAuNzUuNzUgMCAwIDAgMS41IDBaIiBmaWxsPSIjZmZmIi8+Cjwvc3ZnPgo=" />

  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-f6d365?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="GUI" src="https://img.shields.io/badge/gui-PySide6-74c69d?style=for-the-badge&logo=qt&logoColor=white" />
  <img alt="Package Manager" src="https://img.shields.io/badge/package%20manager-uv-5C3EE8?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyBmaWxsPSJub25lIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAxNiAxNiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KIDxwYXRoIGQ9Im0wLjA1NDk3NiAwLjEyNTAzIDAuMDMzMzU2IDcuOTExNyAwLjAyNjY4MyA2LjMyOTNjMC4wMDM2OSAwLjg3Mzg5IDAuNzE1MTEgMS41NzkzIDEuNTg5IDEuNTc1N2wxMC42ODctMC4wNDUwN2MwLjg3MTI4LTAuMDAzNyAxLjU3NTctMC43MjU4NiAxLjU3NTctMS41OTcyaDAuNzI0NzJ2MS41ODJsMS4yNTMyIDEuNTllLTQgLTAuMDY2NzMtMTUuODIzLTcuMjc4NyAwLjAzMDY4OSAwLjAzMDY5OSA2LjMwNnYzLjk0ODVoLTEuMjk2NmwwLjAzMDY5OS0zLjk0MzEtMC4wMzA2OTktNi4zMDZ6IiBmaWxsPSIjZmZmIiBzdHJva2Utd2lkdGg9Ii4zOTU1OSIvPgo8L3N2Zz4K" />
  <img alt="Ruff" src="https://img.shields.io/badge/lint-ruff-d7ff64?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyBhcmlhLWxhYmVsPSJSdWZmIiByb2xlPSJpbWciIHZlcnNpb249IjEuMSIgdmlld0JveD0iMCAwIDE2IDE2IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHRpdGxlPlJ1ZmY8L3RpdGxlPgogPGNsaXBQYXRoIGlkPSJyIj4KICA8cmVjdCB3aWR0aD0iNTEiIGhlaWdodD0iMjAiIHJ4PSIzIiBmaWxsPSIjZmZmIi8+CiA8L2NsaXBQYXRoPgogPHBhdGggZD0ibTAuMDUwNzM0IDcuOTc0NnYtNy45NzQ2aDcuNTM0N2M2Ljk2MTkgMCA3LjU2ODEgMC4wMzY5NTYgNy45NzQ2IDAuNDg2MTIgMC4zNTk4OSAwLjM5NzY4IDAuNDM5OTMgMS4wODk3IDAuNDM5OTMgMy44MDM2IDAgMy44OTY4LTAuMTM2ODIgNC4yMDc0LTEuOTQzNCA0LjQxMS0wLjk5MDI4IDAuMTExNjItMS4yNDY1IDAuMjQyNjYtMS4yNDY1IDAuNjM3NTcgMCAwLjQzMDMyIDAuMjE0MTkgMC40OTcwNyAxLjU5NDkgMC40OTcwN2gxLjU5NDl2Ni4xMTM5aC03LjQ0M3YtMi4zOTI0YzAtMi4yMTUyLTAuMDM5MzgzLTIuMzkyNC0wLjUzMTY0LTIuMzkyNC0wLjQ5MjI2IDAtMC41MzE2NCAwLjE3NzIyLTAuNTMxNjQgMi4zOTI0djIuMzkyNGgtNy40NDN6bTkuODM1NC0xLjMyOTFjMC0wLjQ4MTAxLTAuMTc3MjEtMC41MzE2NC0xLjg2MDctMC41MzE2NHMtMS44NjA3IDAuMDUwNjMyLTEuODYwNyAwLjUzMTY0YzAgMC40ODEwMSAwLjE3NzIxIDAuNTMxNjQgMS44NjA3IDAuNTMxNjRzMS44NjA3LTAuMDUwNjMyIDEuODYwNy0wLjUzMTY0eiIgZmlsbD0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjEzOTIiLz4KPC9zdmc+Cg==" />
  <a href="https://github.com/ikajdan/steammetadatatool/releases">
  <img alt="AppImage" src="https://img.shields.io/badge/AppImage-available-8ecae6?style=for-the-badge&logo=appimage&logoColor=white" />
  </a>
  <img alt="Linux" src="https://img.shields.io/badge/Linux-supported-2a9d8f?style=for-the-badge&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTZtbSIgaGVpZ2h0PSIxNm1tIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCA1Ni42OTMgNTYuNjkzIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPGcgdHJhbnNmb3JtPSJtYXRyaXgoLjE3OTUgMCAwIC4xNzk1IDQwLjI5IDM4LjQyNykiPgogIDxjaXJjbGUgY3g9Ii00NTMuMzUiIGN5PSItNTQzLjU0IiByPSIwIiBjb2xvcj0iIzAwMDAwMCIgY29sb3ItcmVuZGVyaW5nPSJhdXRvIiBmaWxsPSIjZmZmIiBpbWFnZS1yZW5kZXJpbmc9ImF1dG8iIHNoYXBlLXJlbmRlcmluZz0iYXV0byIgc29saWQtY29sb3I9IiMwMDAwMDAiIHN0eWxlPSJpc29sYXRpb246YXV0bzttaXgtYmxlbmQtbW9kZTpub3JtYWwiLz4KICA8ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtNi43MjEzIC0xMS4yNzEpIj48L2c+CiAgPGNpcmNsZSBjeD0iLTQ0My45NSIgY3k9Ii0xNDEuMTIiIHI9IjAiIGNvbG9yPSIjMDAwMDAwIiBjb2xvci1yZW5kZXJpbmc9ImF1dG8iIGZpbGw9IiNmZmYiIGltYWdlLXJlbmRlcmluZz0iYXV0byIgc2hhcGUtcmVuZGVyaW5nPSJhdXRvIiBzb2xpZC1jb2xvcj0iIzAwMDAwMCIgc3R5bGU9Imlzb2xhdGlvbjphdXRvO21peC1ibGVuZC1tb2RlOm5vcm1hbCIvPgogIDxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKDIuNjc1MiAzOTEuMTUpIj48L2c+CiAgPGNpcmNsZSBjeD0iLTEwMS4yOCIgY3k9Ii0xNDEuMTIiIHI9IjAiIGNvbG9yPSIjMDAwMDAwIiBjb2xvci1yZW5kZXJpbmc9ImF1dG8iIGZpbGw9IiNmZmYiIGltYWdlLXJlbmRlcmluZz0iYXV0byIgc2hhcGUtcmVuZGVyaW5nPSJhdXRvIiBzb2xpZC1jb2xvcj0iIzAwMDAwMCIgc3R5bGU9Imlzb2xhdGlvbjphdXRvO21peC1ibGVuZC1tb2RlOm5vcm1hbCIvPgogIDxjaXJjbGUgY3g9IjIwNS40MSIgY3k9Ii0xNDEuMTIiIHI9IjAiIGNvbG9yPSIjMDAwMDAwIiBjb2xvci1yZW5kZXJpbmc9ImF1dG8iIGZpbGw9IiNmZmYiIGltYWdlLXJlbmRlcmluZz0iYXV0byIgc2hhcGUtcmVuZGVyaW5nPSJhdXRvIiBzb2xpZC1jb2xvcj0iIzAwMDAwMCIgc3R5bGU9Imlzb2xhdGlvbjphdXRvO21peC1ibGVuZC1tb2RlOm5vcm1hbCIvPgogIDxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKDY1Mi4wNCAzOTEuMTUpIj48L2c+CiAgPGcgZmlsbD0iI2ZmZiI+CiAgIDxwYXRoIGQ9Im0tNjYuNTM3LTIxNC4xYy0xLjA0NDMtOGUtNSAtMi4yNzQ0IDAuMDA3OS0zLjI4NDYgMC4wMTAyLTIzLjg1NyAwLjczNDIxLTQ4LjEzIDYuMDMyNC02NC40NzggMjguNjc0LTE3Ljg1IDI0LjcyMi0xMi45MDQgNDYuOTkyLTEzLjYxOCA1NC44NDktMC43MTQyOCA3Ljg1NzItNTQuMTEyIDk5LjMwNC00Ny4wMDUgMTEyLjM2IDMuOTcxNiA3LjI5NiAyMS42NDYtNC4zNTkyIDIyLjAwMyA1Ljk5OCAwLjM1NzE1IDEwLjM1Ny0xNy4yNjkgMTE0IDEwNS40NiAxMTRoMC45MTgwNmMwLjMxODcxIDQuMWUtNCAwLjYxNTgxLTAuMDAzMDEgMC45MTgwNiAwIDEyMi43MyAwIDEwNS4xMS0xMDMuNjUgMTA1LjQ2LTExNCAwLjM1NzE0LTEwLjM1NyAxOC4wMzEgMS4yOTggMjIuMDAzLTUuOTk4IDcuMTA3LTEzLjA1Ni00Ni4yOS0xMDQuNS00Ny4wMDUtMTEyLjM2LTAuNzE0MjktNy44NTcxIDQuMjIyMi0zMC4xMjYtMTMuNjI4LTU0Ljg0OS0xNi4zNDgtMjIuNjQyLTQwLjYxMS0yNy45NC02NC40NjgtMjguNjc0LTEuMjQxIDAtMi4xNzM3LTAuMDEwMi0zLjI4NDYtMC4wMTAyem0tMzkuOTk3IDU2LjQ0YzYuNDg5NCAwIDExLjc1MSA1LjI2MTggMTEuNzUxIDExLjc1MXMtNS4yNjE4IDExLjc0MS0xMS43NTEgMTEuNzQxLTExLjc1MS01LjI1MTYtMTEuNzUxLTExLjc0MSA1LjI2MTgtMTEuNzUxIDExLjc1MS0xMS43NTF6bTc5Ljk5MyAwYzYuNDg5NCAwIDExLjc1MSA1LjI2MTggMTEuNzUxIDExLjc1MXMtNS4yNjE4IDExLjc0MS0xMS43NTEgMTEuNzQxLTExLjc1MS01LjI1MTYtMTEuNzUxLTExLjc0MSA1LjI2MTgtMTEuNzUxIDExLjc1MS0xMS43NTF6bS04Ny41NDIgNTMuMzQ5YzEyLjA3LTAuMzg4NSAzNC44NDUgMTcuMDcgNDUuMjMgMjAuNTEzIDEuMTA5MyAwLjI5NzI1IDEuNTE1MiAwLjU0MDYzIDIuMzE1NSAwLjU0MDYzczEuMjYyMy0wLjI2MTE1IDIuMzA1My0wLjU0MDYzYzEwLjc1NS0zLjU2NDkgMzQuODE3LTIyLjE2OSA0Ni40OTUtMjAuNDAxIDEyLjkwOCAxLjk1NDUgMi4yMDE3IDIxLjMyOCA3LjcwMTUgMzUuNTcgMTMuODQzIDM1Ljg0OCAzMi40NTQgOTEuMzc3IDEyLjU5OCAxMjMuNy02LjE3MyAxMC4wNS0yMC41MTUgMjcuMjk5LTY1Ljg4NiAyNy44NjgtMS4wNzEyIDdlLTMgLTIuMTIxNCAwLjAxODcwMS0zLjIxMzIgMC4wMjA0MDEtMS4wOTI0LTJlLTMgLTIuMTQxNC0wLjAxMzMwMS0zLjIxMzItMC4wMjA0MDEtNDUuMzY4LTAuNTcwMTItNTkuNzEzLTE3LjgxOC02NS44ODYtMjcuODY4LTE5Ljg1Ni0zMi4zMjctMS4yNDU1LTg3Ljg1NSAxMi41OTgtMTIzLjcgNS40OTk4LTE0LjI0Mi01LjIwNjgtMzMuNjE1IDcuNzAxNS0zNS41NyAwLjQwMzM4LTAuMDYxMSAwLjgyMjgxLTAuMDk4MjggMS4yNTQ3LTAuMTEyMjF6IiBjb2xvcj0iIzAwMDAwMCIgY29sb3ItcmVuZGVyaW5nPSJhdXRvIiBmaWxsPSIjZmZmIiBpbWFnZS1yZW5kZXJpbmc9ImF1dG8iIHNoYXBlLXJlbmRlcmluZz0iYXV0byIgc29saWQtY29sb3I9IiMwMDAwMDAiIHN0eWxlPSJpc29sYXRpb246YXV0bzttaXgtYmxlbmQtbW9kZTpub3JtYWwiLz4KICA8L2c+CiA8L2c+Cjwvc3ZnPgo=" />
  <img alt="Windows" src="https://img.shields.io/badge/Windows-planned-0078D4?style=for-the-badge&&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAxNiAxNiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KIDxwYXRoIGQ9Im0wIDBoNy41ODQ4djcuNTgxNWgtNy41ODQ4em04LjQxNTIgMGg3LjU4NDh2Ny41ODE1aC03LjU4NDh6bS04LjQxNTIgOC40MTUyaDcuNTg0OHY3LjU4NDhoLTcuNTg0OHptOC40MTUyIDBoNy41ODQ4djcuNTg0OGgtNy41ODQ4IiBmaWxsPSIjZmZmIiBzdHJva2Utd2lkdGg9Ii4wMDMyODIiLz4KPC9zdmc+Cg==" />
  <img alt="macOS" src="https://img.shields.io/badge/macOS-planned-000000?style=for-the-badge&logo=apple&logoColor=white" />
</p>

<br>

<h1 align="center">
  <img src="data/sc-apps-steammetadatatool.svg" alt="SteamMetadataTool Logo" width="192" height="auto"/>
  <br><br>
  SteamMetadataTool
  <br><br>
</h1>

<p align="center">
  <a href="#top">Overview</a> •
  <a href="#screenshots">Screenshots</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#editing">Editing</a> •
  <a href="#license">License</a>
</p>

SteamMetadataTool is a desktop and command-line utility for inspecting and customizing game metadata used by the Steam client. It can browse installed apps, export metadata, and apply local overrides without replacing the original workflow.

- List app IDs and game names from a local Steam installation.
- Export app records as JSON for inspection or backup.
- Edit names, sort-as values, aliases, release dates, and other metadata fields.
- Set custom Steam library artwork, including capsules, headers, heroes, logos, and icons.
- Preview, save, and apply metadata overrides.

The GUI provides a searchable app list, metadata filtering, app detail preview, and dialog for editing metadata values. It also shows Steam library assets and supports choosing between original and custom artwork variants from per-app asset folders.

> [!NOTE]
> This tool is not affiliated with Valve Corporation or Steam.
>
> Steam is a registered trademark of Valve Corporation and is referenced solely for descriptive purposes.

## Screenshots

<p align="center">
  <img src="https://github.com/user-attachments/assets/7cdf595d-8101-456c-8994-a22b99442877" width="49%">
  <img src="https://github.com/user-attachments/assets/06192c40-c9cc-4f9e-9fba-60032736d436" width="49%">
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/2f4829a8-d177-4f06-a551-a5a429415d13" width="49%">
</p>

## Installation

The tool is split into two components: a CLI and a GUI.

### CLI

To install the CLI only:

```bash
uv sync
```

### GUI

To install the GUI and CLI together:

```bash
uv sync --extra gui
```

## Usage

### CLI

List apps:

```bash
uv run steammetadatatool-cli
```

Dump an app as JSON:

```bash
uv run steammetadatatool-cli --appid 10 --json | python -m json.tool
```

### GUI

To use the windowed GUI:

```bash
uv run --extra gui steammetadatatool-gui
```

The main window shows a list of installed apps with their names and IDs. Clicking on an app displays its metadata in the right pane, including library assets. The _Edit Metadata_ button opens a dialog to modify metadata fields. The _Edit Assets_ button allows setting custom library artwork by selecting image files for each asset type.

Steam library assets are images that represent games in the Steam library. Each asset type has specific size requirements:

| Asset   | Required size                   |
| ------- | ------------------------------- |
| Capsule | 600 px by 900 px                |
| Header  | 920 px by 430 px                |
| Hero    | 3840 px by 1240 px              |
| Logo    | 1280 px wide and/or 720 px tall |
| Icon    | 184 px by 184 px                |

The full specification can be found at: <https://partner.steamgames.com/doc/store/assets>.

> [!TIP]
> Steam Library asset changes might not refresh immediately in the Steam client.
> If updated artwork does not appear right away, switch to another game and back,
> or restart the Steam client.

## Editing

Apply per-app metadata overrides:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --sort-as "cs" \
  --aliases "cs, 16" \
  --steam-release-date 2000-11-08
```

Dry-run (no write):

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --dry-run
```

Write metadata overrides to a JSON file:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --metadata-file metadata.json
```

Apply metadata overrides from a JSON file for a specific app:

```bash
uv run steammetadatatool-cli \
  --metadata-file metadata.json \
  --appid 10
```

Apply metadata overrides from a JSON file for all apps:

```bash
uv run steammetadatatool-cli \
  --metadata-file metadata.json
```

Set arbitrary KV path:

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --set appinfo.common.sortas="cs" \
  --set appinfo.common.original_release_date=946684800
```

### Write to a new file

```bash
uv run steammetadatatool-cli \
  --appid 10 \
  --name "Counter-Strike 1.6" \
  --aliases "cs, 16" \
  --write-out /tmp/appinfo.vdf
```

## License

This project is licensed under the GNU General Public License version 3 or later. See the [LICENSE](LICENSE.md) file for details. The application logo is not covered by the GNU GPL v3 or later and may not be used without prior permission.

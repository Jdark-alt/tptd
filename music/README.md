# Menu music

Put the menu music here as `menu.mp3`. The game plays it on the start screen and in a room's lobby, from the press on
**Start playing** until a match begins, looping, and the speaker button (or M) mutes it.

- GitHub Pages serves this folder as it is; on Render, `server.js` serves `music/` (MP3, OGG, M4A or WAV).
- Opened as a file, it works if `music/menu.mp3` sits beside `index.html`.
- Without the file (or in the Claude artifact copy) the game plays a short theme on its synthesiser instead.
- To use another name or format, change `MUSIC_URL` near the top of the music section in `index.html`.

Keep it small (a minute or two at 128–160 kbps loops well and stays under 3 MB) and use music you have the rights to.

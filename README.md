# Koru
Open-source Discord alternative that respects your privacy.

## dev-env quickstart
1. clone the repo  
2. copy koru_settings-example.py to koru_settings.py  
3. define any custom settings u might want  
4. Make sure uv is installed: `pip install uv`  
5. `uv venv` and then run `uv sync`

dont wanna install uv? we have regular requirements.txt files too!  
instead of running steps 4 and 5, run `python3 -m venv .venv`, `source .venv/bin/activate`, and then `pip install -r requirements-dev.txt`

## Django apps
`core` - contains the main stuff like messages, spaces (Koru's equivalent of servers), group chats, etc.
`users` - serves as an extension of the user model. Also contains user settings.
`applications` - Developer applications. Think the developer portal.

## License
Koru - A privacy-focused, open-source Discord alternative.
Copyright (C) 2026 The Koru maintainers

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ia-song-for-2-pc-
Le song pour 2 pc dans 1 seule casque 

Sur le pc cible qui est sur linux

Installer parec
"sudo apt install pulseaudio-utils"

Aller dans le dossier du script et lancer lancer le script
"python3 sender_linux.py 192.168.1.xxx"

Sur le pc windows (serveur)

Aller dans le CMD et lancer 
"pip install soundcard numpy"

Allez dans le dossier où vous avez enregistré mixer_pc1.py
"cd %USERPROFILE%\Downloads"

Lancez l'application
"python mixer_pc1.py"

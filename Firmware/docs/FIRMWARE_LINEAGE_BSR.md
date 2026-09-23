# BSR firmware lineage lock

## Le besoin

BSR distribue trois lignées de logiciel à partir de la même base ODrive/BSR v3.7 :

- **public** : le firmware "générique", librement flashable, aucune restriction, code public.
- **E-dolly-control** : fork BSR pour le robot E-dolly (roue + amortisseur), signé BSR.
- **flight-control-khepri-libel** : fork BSR pour KHEPRI, signé BSR.

Les deux forks BSR peuvent eux-mêmes être publics (code source lisible), le but n'est
pas de cacher l'algorithme. Le but est qu'**une fois qu'une carte a tourné pour la
première fois avec un firmware signé BSR, elle ne doit plus jamais accepter autre
chose que ce même firmware (ou ses mises à jour)** — ni le firmware public, ni
l'autre fork, ni une copie modifiée du même code à laquelle on aurait retiré la
vérification. Objectif concret : empêcher qu'une carte "adoptée" par un produit soit
détournée vers un autre produit, ou reflashée pour contourner des restrictions,
via les outils de flashage standards (dfu-util, odrivetool, STM32CubeProgrammer).

## Le mécanisme existant dont on s'inspire

ODrive (et BSR) utilisent déjà exactement ce genre de verrou, mais pour la version
matérielle plutôt que pour l'identité du logiciel. Dans `Board/v3/board.cpp` :

- `FLASH_OTP_BASE` (`0x1FFF7800`, 528 octets) est une zone **OTP** (*One-Time
  Programmable*) du STM32F405, physiquement séparée de la flash principale.
  Chaque octet ne peut passer que d'1 à 0, jamais l'inverse, et **un effacement
  de masse de la flash principale ne touche jamais cette zone**.
- À la fabrication, ODrive y grave la version matérielle de la carte
  (`HW_VERSION_MAJOR/MINOR/VOLTAGE`, aux offsets 3, 4, 5).
- `check_board_version()`, appelée dès `system_init()`, compare ces octets à
  ce pour quoi CE firmware a été compilé. Si ça ne correspond pas :
  `for (;;);` — blocage silencieux et permanent tant qu'on ne reflashe pas
  le bon firmware.
- `otp_valid_` (`odrive_main.h`) teste juste si l'OTP a été gravé du tout —
  c'est ce qui alimente le message GUI "Not a genuine ODrive" côté
  `tools/odrive/shell.py`. C'est un avertissement, pas un verrou.

Le verrou de filiation logicielle réutilise exactement cette même zone et le
même style de blocage, mais pour vérifier l'identité du *logiciel* plutôt que
celle de la *carte*.

## Disposition OTP

Un nouveau champ, à des offsets qui ne recoupent jamais ceux d'ODrive (0, 3,
4, 5) ni les 16 octets de verrouillage de blocs en toute fin de zone OTP
(offsets 512-527, qui ont une signification matérielle spéciale et ne
doivent jamais être touchés par erreur) :

| Offset | Taille | Contenu |
|---|---|---|
| 32 | 1 octet | Magic de filiation : `0xFF` = carte vierge (jamais revendiquée), `0x00` = revendiquée |
| 33 | 1 octet | Identifiant produit revendiqué (`BsrProductId` : 1 = E-dolly-control, 2 = flight-control-khepri-libel) |
| 34-49 | 16 octets | Empreinte de la clé de signature (16 premiers octets de `sha256(clé_publique)`) |

## Machine à états (`check_firmware_lineage()`, `Board/v3/board.cpp`)

Au démarrage, juste après `check_board_version()` :

1. Le firmware vérifie sa propre signature (voir "Statut" ci-dessous — pour
   l'instant cette étape est un stub qui retourne toujours vrai).
2. Si l'OTP de filiation est vierge (`0xFF`) : cette carte n'a encore jamais
   été revendiquée par un firmware signé BSR. On grave le produit + l'empreinte
   de clé de CE firmware, et on démarre normalement (`CLAIMED_NOW`).
3. Si l'OTP est déjà gravé : le firmware qui tourne doit correspondre
   exactement (même produit, même clé). Sinon : `for (;;);`, comme pour
   `check_board_version()`.

Le firmware **public** ne définit jamais `BSR_PRODUCT_ID` (voir
`Tupfile.lua`, option `CONFIG_BSR_PRODUCT`) : tout ce bloc de code est compilé
en dehors du build public (`#if defined(BSR_PRODUCT_ID)`), donc le firmware
public ne revendique jamais une carte et n'est jamais bloqué par ce
mécanisme — il reste flashable librement sur une carte vierge, exactement
comme aujourd'hui.

## Statut actuel : SIMULATION UNIQUEMENT (phase 1)

Ce qui est implémenté et mergé (`Board/v3/board.cpp`, `bsr_signing_keys.cpp`,
`Tupfile.lua`) :

- La machine à états complète (`check_firmware_lineage()`), testée par
  `firmware_lineage_demo()` (même esprit que `NVM_demo()` dans
  `stm32_nvm.c`) — un test qui joue les 4 scénarios (carte vierge, même
  firmware, produit différent, clé différente) et **affiche** ce qui se
  passerait, sans jamais réellement bloquer la carte.
- Une paire de clés Ed25519 générée pour chacun des deux forks (clés
  publiques dans `bsr_signing_keys.cpp`, clés privées livrées séparément,
  hors dépôt — voir "Gestion des clés" plus bas).
- L'option de build `CONFIG_BSR_PRODUCT` (`edolly` / `khepri`).

Ce qui n'est **volontairement pas encore implémenté**, pour ne prendre aucun
risque de braquer une carte réelle avant revue et tests complets :

- **Gravure OTP réelle.** `otp_lineage_burn_simulated()` ne touche que
  `fake_otp` (RAM). Sur une carte réelle, rien n'est jamais gravé pour
  l'instant — le mécanisme est donc sans danger à flasher dès aujourd'hui,
  mais il ne verrouille encore rien en pratique.
- **Vérification de signature réelle.** `bsr_verify_running_image_signature()`
  retourne toujours `true`. Il faut : vendoriser une implémentation Ed25519
  compacte et éprouvée (vérification seule, pas de signature embarquée),
  réserver un emplacement de signature via le script de lien, et ajouter une
  étape de build qui signe le binaire final (hors dépôt, avec la clé
  privée) puis patche la signature dans l'emplacement réservé.
- **WRP / RDP.** Sans protection en écriture (WRP) sur le secteur contenant
  ce code, et sans protection en lecture (RDP niveau 1), un reflash DFU
  classique avec un firmware modifié (vérification retirée) réussirait tout
  simplement. Poser WRP+RDP au moment de la revendication (étape 2 de la
  machine à états) est ce qui rend un reflash "normal" impossible sans
  d'abord accepter un effacement complet de la flash principale (déclenché
  automatiquement par le matériel dès qu'on rétrograde le RDP) — l'OTP, lui,
  survit toujours à cet effacement.
  Note : NB — ces registres n'ont encore jamais été touchés par ce projet.
  À tester d'abord sur une carte de rebut, jamais sur une carte de vol.

Note trouvée au passage dans `Tupfile.lua` : ODrive prévoit déjà un mécanisme
comparable pour sa carte v4/Pro (`crypto_pkg`, SHA-256 + RSA embarqué,
référencé par `board_v4`) — mais les fichiers sources correspondants
(`Private/ThirdParty/sha-2`, `Private/ThirdParty/rsa_embedded`) ne sont pas
présents dans ce dépôt (partie fermée d'ODrive). On ne peut donc pas les
réutiliser tels quels ; Ed25519 (déjà choisi ici) est de toute façon plus
adapté qu'RSA à un simple usage "vérification seule" sur un MCU contraint.

## Limites honnêtes (à ne jamais perdre de vue)

Le STM32F405 n'a **pas** de démarrage sécurisé matériel (pas de TrustZone
comme sur les STM32H5/L5 récents). Donc, même une fois la phase 2 terminée
(signature réelle + WRP + RDP) :

- Ce verrou arrête très efficacement **le scénario réaliste que tu
  décris** : un client, un revendeur ou un concurrent qui utilise les
  outils de flashage standards (dfu-util, odrivetool, STM32CubeProgrammer)
  pour reflasher une carte déjà adoptée avec le firmware public ou l'autre
  fork.
- Il n'arrête **pas** quelqu'un qui viendrait avec un programmateur
  matériel SWD/JTAG pour faire un effacement bas niveau puis écrire du code
  totalement personnalisé qui ignore l'OTP : rien dans la puce elle-même ne
  force ce code-là à repasser par une vérification. C'est une limite
  fondamentale de faire ça en pur logiciel sur ce MCU, pas un bug de notre
  implémentation.
- Pour fermer complètement cette dernière porte, il faudrait un ancrage
  matériel externe inclonable — par exemple un petit composant sécurisé
  (Microchip ATECC608B ou équivalent, quelques centimes en volume) qui
  autoriserait l'activation des drivers moteur par défi-réponse
  cryptographique. C'est une question de révision de carte (v3.8), pas
  quelque chose d'ajoutable en pur firmware sur les v3.7 déjà produites.

## Gestion des clés

Une paire de clés Ed25519 a été générée par fork (2026-09-23). Les clés
**publiques** sont dans `bsr_signing_keys.cpp` (ce dépôt). Les clés
**privées** ont été livrées séparément, hors dépôt, hors de tout historique
git — même dans un fork "privé", puisque ces forks sont eux-mêmes appelés à
devenir des dépôts non-privés. Elles ne doivent jamais être commitées nulle
part ; à conserver hors-ligne (coffre-fort numérique / gestionnaire de
mots de passe), avec une sauvegarde séparée. Une clé privée compromise ou
perdue signifie : plus aucune mise à jour légitime possible pour les cartes
déjà revendiquées par ce fork tant qu'un nouveau mécanisme de rotation de
clé n'est pas mis en place (non conçu à ce stade).

## Prochaine étape proposée

Ne rien activer sur du matériel réel avant d'avoir, dans l'ordre : (1) fait
tourner `firmware_lineage_demo()` sur une carte de dev réelle pour confirmer
le comportement en simulation, (2) vendorisé et testé la vérification
Ed25519 réelle, (3) testé WRP+RDP sur une carte de rebut explicitement
sacrifiable, jamais sur une carte de vol.

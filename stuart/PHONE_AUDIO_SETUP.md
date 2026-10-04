# S24 Plus audio test setup

ADB is authorized on the SM-S926B running Android 16. Empty call-log/SMS queries succeed. Two controlled outgoing calls were attempted; the second call log shows 16 seconds connected. The test terminated because direct WDM-KS Bluetooth playback stopped before supplying a prompt. Speech and keypad capture remain unverified. No real SMS has been sent.

## Next candidate route

Stuart WAV → CABLE Input playback → CABLE Output microphone → Phone Link → remote caller.

Remote caller → Phone Link → Realtek speaker playback → WASAPI loopback → Stuart mono PCM16.

One virtual cable is used for transmit; speaker-loopback provides a separate receive path. Phone Link must actually use the selected PC microphone and speaker. This is a candidate to validate, not proven hardware compatibility. Keep other app audio quiet during the controlled test because loopback includes everything on the selected speaker.

## Human installation step

The official VB-CABLE package is extracted at `stuart/runtime/tools/vb-cable/`. Its `VBCABLE_Setup_x64.exe` signature was verified as valid, signed by BUREL VINCENT Entrepreneur individuel. All package files must stay together.

1. Save your work and close any active calls.
2. Right-click `VBCABLE_Setup_x64.exe` and choose **Run as administrator**.
3. Choose **Install Driver** in the installer.
4. Reboot Windows as the vendor instructs. This stops local demo services; no source or saved transport records are lost.
5. Return to this chat and say that installation and restart are complete.

Official source and installation instructions: https://vb-audio.com/Cable/

## After reboot, with Meet present

Recheck ADB authorization and Phone Link pairing. List audio devices again; indices can change after installing a driver. Do not reuse old index 36/37 from the failed Bluetooth test.

In Windows Sound settings, choose the new CABLE Output device as the PC input used by Phone Link, and Realtek Speaker as its output. Record the prior default microphone so it can be restored after the demo. Close and reopen Phone Link after changing its input. Confirm the route through a controlled call before enabling automatic callbacks.

Set Stuart's transmit output to the corresponding **CABLE Input** playback endpoint. Set the receive input to `loopback:Speaker (Realtek(R) Audio)` using the exact current device name from `python -m stuart devices`. The service checks receive availability before dialing. It cannot prove Phone Link's routing from endpoint names.

Test transmit tone first, then remote keypad, then a short nonclinical phrase. Hang up on failures. Once both directions work, use the actual Bob integration and test missed-call detection; leave ordinary incoming calls outside synthetic-Bob testing.

The simulator can be restarted with `./Start-Demo.ps1`. Its three scripted lines and encrypted loopback sync remain separate from these physical capability tests.

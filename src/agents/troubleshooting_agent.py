from typing import Dict, Any, List, Optional
import logging


try:
    from google.adk.agents.llm_agent import Agent  
except Exception:
    Agent = None

logger = logging.getLogger("troubleshooting_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

TROUBLESHOOT_INSTRUCTION = """
You are the Troubleshooting Agent.

Your job:
1. Parse the user's description to identify:
   - device_type (e.g., laptop, printer, CCTV, desktop)
   - key symptoms (e.g., won't turn on, beeping, paper jam, no video)
2. If device_type or key symptoms are missing, ask a concise clarifying question.
3. Provide a short set (3-6) of prioritized troubleshooting steps tailored to the device & symptoms.
4. If the issue likely requires board-level or physical repair, advise escalation to a technician.
5. Return output as a JSON-like dict:
   {"status": "ok"|"missing_info"|"escalate", "device_type": <str|null>, "symptoms": [..], "suggestions": [..], "reply": <string>}
Keep replies short, user-friendly and safe.
"""

def build_troubleshooting_agent(model_name: str = "gemini-1") -> Any:
    if Agent is None:
        raise RuntimeError("google.adk is not installed. Cannot create ADK agent.")
    agent = Agent(
        model=model_name,
        name="troubleshooting_agent",
        description="LLM-powered agent that provides diagnostic suggestions.",
        instruction=TROUBLESHOOT_INSTRUCTION,
        tools=[],  
    )
    return agent


def local_troubleshoot_process(text: str) -> Dict[str, Any]:
    """
    A heuristic-based local troubleshooting helper.
    Returns a dict similar to the ADK agent output for testing/demo.
    """
    t = (text or "").lower()
    device: Optional[str] = None
    symptoms: List[str] = []

    # detect device
    if any(k in t for k in ["laptop", "notebook"]):
        device = "laptop"
    elif any(k in t for k in ["printer", "inkjet", "laser", "hp", "canon", "epson"]):
        device = "printer"
    elif any(k in t for k in ["cctv", "camera", "dvr", "nvr"]):
        device = "cctv"
    elif any(k in t for k in ["desktop", "pc", "workstation"]):
        device = "desktop"
    else:
        device = None

    if any(k in t for k in ["won't turn on", "not turning", "no power", "won't power", "won't boot", "won't start"]):
        symptoms.append("no_power")
    if any(k in t for k in ["beep", "beeping"]):
        symptoms.append("beeping")
    if any(k in t for k in ["no display", "no video", "black screen", "no signal"]):
        symptoms.append("no_display")
    if any(k in t for k in ["paper jam", "jam", "paper stuck"]):
        symptoms.append("paper_jam")
    if any(k in t for k in ["not printing", "prints blank", "blank pages", "printer error"]):
        symptoms.append("not_printing")
    if any(k in t for k in ["overheat", "hot", "heating"]):
        symptoms.append("overheat")
    if any(k in t for k in ["slow", "lag", "freeze", "freez", "frozen"]):
        symptoms.append("slow_performance")
    if any(k in t for k in ["error", "error code", "error message", "code:"]):
        symptoms.append("error_message")
    if any(k in t for k in ["disconnect", "no network", "offline", "disconnecting"]):
        symptoms.append("network_issue")

    if not device or not symptoms:
        missing = []
        if not device:
            missing.append("device_type")
        if not symptoms:
            missing.append("symptoms")
        reply = "Could you tell me the device type (e.g., laptop, printer) and the exact symptoms or error messages?"
        logger.info("Missing fields for troubleshooting: %s", missing)
        return {
            "status": "missing_info",
            "missing": missing,
            "reply": reply
        }


    suggestions: List[str] = []
    status = "ok"

    if device == "laptop":
        if "no_power" in symptoms:
            suggestions.extend([
                "Check that the charger is firmly connected and the power LED on the charger is lit.",
                "Try a different power outlet and, if available, a different compatible charger.",
                "Remove battery (if removable) and try powering with adapter only.",
                "If still no power, escalate for board-level inspection (possible DC jack or motherboard issue)."
            ])
            status = "escalate"
        elif "no_display" in symptoms:
            suggestions.extend([
                "Check display brightness and try an external monitor via HDMI/VGA.",
                "Listen for fan activity; reseat RAM modules and try again.",
                "If external monitor works, the laptop screen or cable may be faulty."
            ])
            status = "ok"
        elif "beeping" in symptoms:
            suggestions.extend([
                "Count beeps and note the pattern; it indicates POST error (RAM, GPU, CPU).",
                "Try reseating RAM modules and boot again.",
                "If beeps persist, escalate to technician for hardware diagnostics."
            ])
            status = "ok"
        elif "slow_performance" in symptoms:
            suggestions.extend([
                "Check Task Manager / Activity Monitor for processes using high CPU/RAM.",
                "Reboot the system and apply OS updates.",
                "Run disk cleanup and check for malware/antivirus scans."
            ])
            status = "ok"
        else:
            suggestions.extend(["Try rebooting, ensure OS updates are applied, and run basic antivirus scans."])
            status = "ok"

    elif device == "printer":
        if "paper_jam" in symptoms:
            suggestions.extend([
                "Turn off the printer and gently remove any visible jammed paper.",
                "Open access panels and check rollers for small scraps.",
                "Ensure paper tray is correctly loaded and not overfilled."
            ])
            status = "ok"
        elif "not_printing" in symptoms:
            suggestions.extend([
                "Check printer status on PC and ensure correct driver is selected.",
                "Verify ink/toner levels and try a test print from the printer's onboard menu.",
                "Restart the printer spooler service on your computer."
            ])
            status = "ok"
        else:
            suggestions.append("Power cycle the printer and check for error lights or codes.")
            status = "ok"

    elif device == "cctv":
        if "no_display" in symptoms or "no_power" in symptoms:
            suggestions.extend([
                "Check power connections to camera and NVR/DVR.",
                "Ensure network cable (if IP camera) is connected and switch/router is powered.",
                "Try rebooting the NVR/DVR and check camera status LEDs."
            ])
            status = "ok"
        else:
            suggestions.append("Check camera lens and wiring; if uncertain, capture a photo and bring to technician.")
            status = "ok"

    elif device == "desktop":
        if "no_power" in symptoms:
            suggestions.extend([
                "Check PSU switch and power cable; test with another power cable.",
                "Try booting with minimal peripherals (disconnect USB devices).",
                "If still no power, escalate for PSU/motherboard inspection."
            ])
            status = "escalate"
        elif "no_display" in symptoms:
            suggestions.extend([
                "Ensure monitor input is correct and cables are seated.",
                "Reseat GPU and RAM if comfortable doing so; try onboard video if available.",
                "Check for beeps during boot which indicate hardware faults."
            ])
            status = "ok"
        else:
            suggestions.append("Reboot the PC and check BIOS/POST messages for errors.")
            status = "ok"

    else:
        suggestions.append("Try basic troubleshooting: reboot the device, check cables and power, and note any error messages.")
        status = "ok"

    reply = f"Here are suggested steps for your {device}: {suggestions[0]}" if suggestions else "I have some suggestions."

    return {
        "status": status,
        "device_type": device,
        "symptoms": symptoms,
        "suggestions": suggestions,
        "reply": reply
    }


# CLI demo
if __name__ == "__main__":
    examples = [
        "My laptop won't boot after update and the screen is black.",
        "Printer shows paper jam and won't print.",
        "CCTV camera offline, no video on monitor.",
        "My desktop is very slow and freezing frequently."
    ]
    for ex in examples:
        print("-" * 60)
        print("Input:", ex)
        print("Output:", local_troubleshoot_process(ex))

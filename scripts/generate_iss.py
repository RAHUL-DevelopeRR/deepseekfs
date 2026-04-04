import os
import re
from pathlib import Path

def generate_iss():
    root_dir = Path(__file__).resolve().parent.parent
    version_file = root_dir / "version.py"
    template_file = root_dir / "neuron_installer.iss.template"
    output_file = root_dir / "neuron_installer.iss"
    
    # Extract version
    version_content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_content)
    if not match:
        raise ValueError("Could not find __version__ in version.py")
    
    version = match.group(1)
    
    # Ensure VersionInfoVersion format (must be X.Y.Z.W)
    parts = version.split('.')
    while len(parts) < 4:
        parts.append("0")
    version_dots = ".".join(parts[:4])
    
    # Read template and replace
    template_content = template_file.read_text(encoding="utf-8")
    output_content = template_content.replace("{{VERSION}}", version)
    output_content = output_content.replace("{{VERSION_DOTS}}", version_dots)
    
    # Write output
    output_file.write_text(output_content, encoding="utf-8")
    print(f"Generated {output_file.name} with version {version} ({version_dots})")

if __name__ == "__main__":
    generate_iss()

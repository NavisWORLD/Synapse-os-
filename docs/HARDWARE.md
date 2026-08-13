# Hardware Guide

## Intel / AMD graphics

The image includes Mesa/Vulkan userspace and common Debian firmware packages. Modern integrated graphics should use the kernel/Mesa path by default.

## NVIDIA

The base image does not force a proprietary NVIDIA driver because driver choice depends on GPU generation, Secure Boot, and current Debian packaging. Test the live session first, then install the appropriate Debian-supported driver after installation if needed.

## Wi-Fi

Common Intel and Realtek firmware packages are included. Unusual vendor devices may need additional firmware.

## Thermals and power

Synapse OS does not disable firmware thermal limits, overclock hardware, or force one I/O scheduler across every disk type. Those changes are hardware-specific and must be benchmarked before being made defaults.

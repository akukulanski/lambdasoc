import os

from .base import *
from ..cpu import CPU
from ..periph.intc import InterruptController
from ..periph.sram import SRAMPeripheral
from ..periph.sdram import SDRAMPeripheral
from ..periph.serial import AsyncSerialPeripheral
from ..periph.timer import TimerPeripheral


__all__ = ["CPUSoC", "BIOSBuilder"]


class CPUSoC(SoC):
    cpu    = socproperty(CPU)
    intc   = socproperty(InterruptController)
    rom    = socproperty(SRAMPeripheral)
    ram    = socproperty(SRAMPeripheral)
    sdram  = socproperty(SDRAMPeripheral, weak=True)
    uart   = socproperty(AsyncSerialPeripheral)
    timer  = socproperty(TimerPeripheral)

    # TODO: implement a CRG peripheral and expose clock frequencies through CSRs.
    clk_freq = socproperty(int)

    def build(self, name=None,
              litedram_dir="build/litedram",
              build_dir="build/soc", do_build=True,
              do_init=False):
        """TODO
        """
        plan = BIOSBuilder().prepare(self, build_dir, name,
                                     litedram_dir=os.path.abspath(litedram_dir))
        if not do_build:
            return plan

        products = plan.execute_local(build_dir)
        if not do_init:
            return products

        with products.extract("bios/bios.bin") as bios_filename:
            with open(bios_filename, "rb") as f:
                words = iter(lambda: f.read(self.cpu.data_width // 8), b'')
                bios  = [int.from_bytes(w, self.cpu.byteorder) for w in words]
        self.rom.init = bios


class BIOSBuilder(ConfigBuilder):
    file_templates = {
        **ConfigBuilder.file_templates,
        "{{name}}.config": r"""
            # {{autogenerated}}
            CONFIG_CPU_{{soc.cpu.name.upper()}}=y
            CONFIG_CPU_RESET_ADDR={{hex(soc.cpu.reset_addr)}}
            CONFIG_CPU_BYTEORDER="{{soc.cpu.byteorder}}"
            CONFIG_ARCH_{{soc.cpu.arch.upper()}}=y
            {% if soc.cpu.muldiv == "soft" %}
            CONFIG_{{soc.cpu.arch.upper()}}_MULDIV_SOFT=y
            {% else %}
            CONFIG_{{soc.cpu.arch.upper()}}_MULDIV_SOFT=n
            {% endif %}
            CONFIG_ROM_START={{hex(periph_addr(soc.rom))}}
            CONFIG_ROM_SIZE={{hex(soc.rom.size)}}
            CONFIG_RAM_START={{hex(periph_addr(soc.ram))}}
            CONFIG_RAM_SIZE={{hex(soc.ram.size)}}
            CONFIG_UART_START={{hex(periph_addr(soc.uart))}}
            CONFIG_UART_IRQNO={{soc.intc.find_index(soc.uart.irq)}}
            CONFIG_UART_RX_RINGBUF_SIZE_LOG2=7
            CONFIG_UART_TX_RINGBUF_SIZE_LOG2=7
            CONFIG_TIMER_START={{hex(periph_addr(soc.timer))}}
            CONFIG_TIMER_IRQNO={{soc.intc.find_index(soc.timer.irq)}}
            CONFIG_TIMER_CTR_WIDTH={{soc.timer.width}}
            CONFIG_CLOCK_FREQ={{soc.clk_freq}}

            {% if soc.sdram is not none %}
            CONFIG_WITH_SDRAM=y
            CONFIG_SDRAM_START={{hex(periph_addr(soc.sdram))}}
            CONFIG_SDRAM_SIZE={{hex(soc.sdram.core.size)}}
            {% else %}
            CONFIG_WITH_SDRAM=n
            {% endif %}
        """,
        "litex_config.h": r"""
            // {{autogenerated}}
            #ifndef __LITEX_CONFIG_H_LAMBDASOC
            #define __LITEX_CONFIG_H_LAMBDASOC

            #define LX_CONFIG_TIMER_START {{hex(periph_addr(soc.timer))}}

            {% if soc.sdram is not none %}
            #define LX_CONFIG_SDRAM_START {{hex(periph_addr(soc.sdram))}}UL
            #define LX_CONFIG_SDRAM_SIZE {{hex(soc.sdram.core.size)}}UL
            #define LX_CONFIG_SDRAM_CACHE_SIZE {{soc.sdram._cache.size}}
            #define LX_CONFIG_MEMTEST_DATA_SIZE 2*1024*1024
            #define LX_CONFIG_MEMTEST_ADDR_SIZE 65536
            {% endif %}

            #endif
        """,
    }
    command_templates = [
        *ConfigBuilder.command_templates,
        r"""
            {% if soc.sdram is not none %}
            litedram_dir={{litedram_dir}}/{{soc.sdram.core.name}}
            {% endif %}
            build={{build_dir}}
            KCONFIG_CONFIG={{build_dir}}/{{name}}.config
            make -C {{software_dir}}/bios 1>&2
        """,
    ]

    def prepare(self, soc, build_dir, name, litedram_dir):
        if not isinstance(soc, CPUSoC):
            raise TypeError("SoC must be an instance of CPUSoC, not {!r}"
                            .format(soc))
        return super().prepare(soc, build_dir, name, litedram_dir=litedram_dir)

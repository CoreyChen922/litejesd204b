from litex.gen import *

from litejesd204b.common import *


class Scrambler(Module):
    """Scrambler
    """
    def __init__(self, dw):
        self.enable = Signal()
        self.data_in = Signal(dw)
        self.data_out = Signal(dw)

        # # #

        state = Signal(15, reset=0x7fff)
        feedback = Signal(dw)
        full = Signal(dw+15)

        self.comb += [
            full.eq(Cat(feedback, state)),
            feedback.eq(full[15:15+dw] ^ full[14:14+dw] ^ self.data_in)
        ]

        self.sync += [
            If(self.enable,
                self.data_out.eq(feedback),
                state.eq(full)
            )
        ]


class AlignmentCharacterInserter(Module):
    """Alignment Character Inserter
    """
    def __init__(self, dw):
        # XXX refactor to operate on // datas
        self.sink = sink = stream.Endpoint(link_layout(dw))
        self.source = source = stream.Endpoint(link_layout(dw))

        # # #

        last_dn = Signal(8)
        dn = Signal(8)
        new_dn = Signal(8)

        self.comb += [
            sink.connect(source),
            dn.eq(sink.data[:8]),
            If(sink.valid & sink.ready,
                If(~sink.scrambled,
                    If(dn == last_dn,
                        If(sink.multiframe_last,
                            new_dn.eq(control_characters["A"])
                        ).Elif(sink.frame_last,
                            new_dn.eq(control_characters["F"])
                        )
                    )
                ).Else(
                    If(dn == 0x7c,
                        If(sink.multiframe_last,
                            new_dn.eq(control_characters["A"])
                        )
                    ).Elif(dn == 0xfc,
                        If(sink.frame_last,
                            new_dn.eq(control_characters["F"])
                        )
                    )
                )
            ),
            If(new_dn,
                source.data.eq(Cat(new_dn, sink.data[8:])),
                source.charisk.eq(1)
            )
        ]

        self.sync += \
            If(sink.valid & sink.ready & sink.frame_last,
                last_dn.eq(dn)
            )


class ILASGenerator(Module):
    """Initial Lane Alignment Sequence Generator
    """
    def __init__(self):
        # TODO
        # 4 or more multiframes
        # last character of each multiframe = A
        # first, third and fourth multiframes first data = R
        # for ADI DACs, data in between is a ramp
        # second multiframe = R, Q, followed by link parameters
        # after the last A character of the last ILAS multiframe, user data starts
        pass


class LinkTX(Module):
    """Link TX layer
    """
    def __init__(self, dw):
        self.reset = Signal()
        self.start = Signal()
        self.ready = Signal()
        self.sync = Signal()

        self.sink = stream.Endpoint(link_layout(dw))
        self.source = stream.Endpoint(link_layout(dw))

        # # #

        #                                       ILAS generator +
        #                                                      + mux --> 8b/10b --> source
        # sink --> scrambler --> alignement_character_inserter +

        self.fsm = fsm = ResetInserter()(FSM(reset_state="RESET"))
        self.submodules += fsm
        self.comb += fsm.reset.eq(self.reset)

        # Init
        fsm.act("RESET",
            If(self.start,
                NextState("CGS")
            )
        )

        # Code Group Syncronization
        fsm.act("CGS",
            self.source.valid.eq(1),
            self.source.data.eq(control_characters["K"]),
            self.source.charisk.eq(2**dw-1),
            If(~self.sync,
                NextState("ILAS")
            )
        )
        # Initial Lane Alignment Sequence
        fsm.act("ILAS",
            # TODO: add ILAS generator
            NextState("USER_DATA")
        )
        # User Data
        fsm.act("USER_DATA",
            self.ready.eq(1),
            self.sink.connect(self.source)
        )

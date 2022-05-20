proc get_tile_types {} {
    set tiles [get_tiles]
    set type {}
    foreach x $tiles {
        set prop [get_property TYPE $x]
        if { [lsearch -exact $type $prop] == -1 } {
            lappend type $prop
            if {[llength [get_pips -of_objects $x]] != 0} {
                puts $prop
            }
        }
    }
    return $type
}

if {[info exists tile_types] != 1} {
      set tile_types [get_tile_types]
}

set tile_types [lsort $tile_types]

puts $tile_types

foreach T_type $tile_types {
    set tile [lindex [get_tiles -filter "TYPE =~ $T_type"] 0]
    # puts "Tile ($T_type) $tile"
#
    set alwys 0
    set dflt 0
    set rtthru 0
    set pp 0

    foreach P [get_pips -of_objects $tile] {

        set P_name [lindex [split $P "."] end]
        set O [lindex [split $P ">"] end]
        set out_list [get_pips -of_objects $tile -filter "NAME=~*$O"]

        # Permanent or pseudo pips are always on
        # They are pips which are the only driver of their output wire
        if {[llength $out_list] == 1} {
            incr alwys
            #puts $::f "\"$P_name\":\{ \"TYPE\":\"ALWAYS\",\"BITS\":\[\] \}"
        # Default pips are essentially pullups and have a name that starts with "VCC_WIRE"
        } elseif {[string first "VCC_WIRE" $P_name] == 0} {
            incr dflt
            #puts $::f "\"$P_name\":\{ \"TYPE\":\"DEFAULT\",\"BITS\":\[\] \}"
        # Route through pips can be determined by the combination of properties below
        } elseif {([get_property IS_BUFFERED_2_1 $P] == 1) && ([get_property IS_PSEUDO $P] == 1)} {
            incr rtthru
            #puts $::f "\"$P_name\":\{ \"TYPE\":\"ROUTETHRU\",\"BITS\":\[\] \}"
        # Everything else is a normal pip
        } else {
            incr pp
            #puts $::f "\"$P_name\":\{ \"TYPE\":\"PIP\",\"BITS\":\[\] \}"
        }
    }    $:lwys:$: ROUTETHRU=$rtthru  PIP=$pp"

}

# Results:

# Tile (BRAM_INT_INTERFACE_L) BRAM_INT_INTERFACE_L_X6Y199    24:0:0:0
# Tile (BRAM_INT_INTERFACE_R) BRAM_INT_INTERFACE_R_X51Y149    24:0:0:0
# Tile (BRAM_L) BRAM_L_X6Y195    590:0:0:384     #############################
# Tile (BRAM_R) BRAM_R_X51Y145    590:0:0:384     #############################
# Tile (BRKH_BRAM) BRKH_BRAM_X19Y156    0:0:0:0
# Tile (BRKH_B_TERM_INT) BRKH_B_TERM_INT_X36Y156    0:0:0:0
# Tile (BRKH_CLB) BRKH_CLB_X2Y149    0:0:0:0
# Tile (BRKH_CLK) BRKH_CLK_X78Y156    0:0:0:0
# Tile (BRKH_CMT) BRKH_CMT_X8Y156    0:0:0:0
# Tile (BRKH_DSP_L) BRKH_DSP_L_X119Y156    0:0:0:0
# Tile (BRKH_DSP_R) BRKH_DSP_R_X28Y156    0:0:0:0
# Tile (BRKH_GTX) BRKH_GTX_X52Y149    0:0:0:12     #############################
# Tile (BRKH_INT) BRKH_INT_X0Y149    14:0:0:0
# Tile (BRKH_TERM_INT) BRKH_TERM_INT_X42Y149    0:0:0:0
# Tile (B_TERM_INT) B_TERM_INT_X4Y0    0:0:0:0
# Tile (CFG_CENTER_BOT) CFG_CENTER_BOT_X46Y63    13:0:0:0
# Tile (CFG_CENTER_MID) CFG_CENTER_MID_X46Y84    285:0:0:0
# Tile (CFG_CENTER_TOP) CFG_CENTER_TOP_X46Y94    38:0:0:0
# Tile (CLBLL_L) CLBLL_L_X2Y199    94:0:52:0
# Tile (CLBLL_R) CLBLL_R_X13Y199    94:0:52:0
# Tile (CLBLM_L) CLBLM_L_X8Y199    99:0:52:0
# Tile (CLBLM_R) CLBLM_R_X3Y199    99:0:52:0
# Tile (CLK_BUFG_BOT_R) CLK_BUFG_BOT_R_X78Y100    144:0:0:160     #############################
# Tile (CLK_BUFG_REBUF) CLK_BUFG_REBUF_X78Y194    64:0:0:32     #############################
# Tile (CLK_BUFG_TOP_R) CLK_BUFG_TOP_R_X78Y105    144:0:0:160     #############################
# Tile (CLK_FEED) CLK_FEED_X78Y207    0:0:0:0
# Tile (CLK_HROW_BOT_R) CLK_HROW_BOT_R_X78Y78    168:0:0:2672     #############################
# Tile (CLK_HROW_TOP_R) CLK_HROW_TOP_R_X78Y182    168:0:0:2672     #############################
# Tile (CLK_MTBF2) CLK_MTBF2_X78Y99    0:0:0:0
# Tile (CLK_PMV) CLK_PMV_X78Y54    0:0:0:0
# Tile (CLK_PMV2) CLK_PMV2_X78Y95    0:0:0:0
# Tile (CLK_PMV2_SVT) CLK_PMV2_SVT_X78Y86    0:0:0:0
# Tile (CLK_PMVIOB) CLK_PMVIOB_X78Y70    0:0:0:0
# Tile (CLK_TERM) CLK_TERM_X78Y208    0:0:0:0
# Tile (CMT_FIFO_L) CMT_FIFO_L_X140Y149    270:0:0:8     #############################
# Tile (CMT_FIFO_R) CMT_FIFO_R_X7Y201    270:0:0:8     #############################
# Tile (CMT_PMV) CMT_PMV_X7Y207    0:0:0:0
# Tile (CMT_PMV_L) CMT_PMV_L_X140Y155    0:0:0:0
# Tile (CMT_TOP_L_LOWER_B) CMT_TOP_L_LOWER_B_X139Y113    160:0:0:39     #############################
# Tile (CMT_TOP_L_LOWER_T) CMT_TOP_L_LOWER_T_X139Y122    238:0:0:42     #############################
# Tile (CMT_TOP_L_UPPER_B) CMT_TOP_L_UPPER_B_X139Y135    330:0:0:57     #############################
# Tile (CMT_TOP_L_UPPER_T) CMT_TOP_L_UPPER_T_X139Y148    136:0:0:19     #############################
# Tile (CMT_TOP_R_LOWER_B) CMT_TOP_R_LOWER_B_X8Y165    160:0:0:39     #############################
# Tile (CMT_TOP_R_LOWER_T) CMT_TOP_R_LOWER_T_X8Y174    238:0:0:42     #############################
# Tile (CMT_TOP_R_UPPER_B) CMT_TOP_R_UPPER_B_X8Y187    330:0:0:57     #############################
# Tile (CMT_TOP_R_UPPER_T) CMT_TOP_R_UPPER_T_X8Y200    136:0:0:19     #############################
# Tile (DSP_L) DSP_L_X48Y195    560:0:0:234     #############################
# Tile (DSP_R) DSP_R_X9Y195    560:0:0:234     #############################
# Tile (GTP_CHANNEL_0) GTP_CHANNEL_0_X130Y162    526:0:0:0
# Tile (GTP_CHANNEL_1) GTP_CHANNEL_1_X130Y173    526:0:0:0
# Tile (GTP_CHANNEL_2) GTP_CHANNEL_2_X130Y191    526:0:0:0
# Tile (GTP_CHANNEL_3) GTP_CHANNEL_3_X130Y202    526:0:0:0
# Tile (GTP_COMMON) GTP_COMMON_X130Y179    157:0:0:4     #############################
# Tile (GTP_INT_INTERFACE) GTP_INT_INTERFACE_X51Y199    72:0:0:96     #############################
# Tile (HCLK_BRAM) HCLK_BRAM_X19Y182    0:0:0:0
# Tile (HCLK_CLB) HCLK_CLB_X10Y182    0:0:0:0
# Tile (HCLK_CMT) HCLK_CMT_X8Y182    8:0:0:974     #############################
# Tile (HCLK_CMT_L) HCLK_CMT_L_X139Y130    8:0:0:974     #############################
# Tile (HCLK_DSP_L) HCLK_DSP_L_X119Y182    0:0:0:0
# Tile (HCLK_DSP_R) HCLK_DSP_R_X28Y182    0:0:0:0
# Tile (HCLK_FEEDTHRU_1) HCLK_FEEDTHRU_1_X35Y130    0:0:0:0
# Tile (HCLK_FEEDTHRU_2) HCLK_FEEDTHRU_2_X36Y130    0:0:0:0
# Tile (HCLK_FIFO_L) HCLK_FIFO_L_X7Y182    0:0:0:0
# Tile (HCLK_GTX) HCLK_GTX_X128Y182    0:0:0:0
# Tile (HCLK_INT_INTERFACE) HCLK_INT_INTERFACE_X3Y182    0:0:0:0
# Tile (HCLK_IOB) HCLK_IOB_X0Y182    0:0:0:0
# Tile (HCLK_IOI3) HCLK_IOI3_X1Y182    48:0:0:196     #############################
# Tile (HCLK_L) HCLK_L_X4Y182    8:0:0:192     #############################
# Tile (HCLK_L_BOT_UTURN) HCLK_L_BOT_UTURN_X105Y182    8:0:0:96     #############################
# Tile (HCLK_R) HCLK_R_X5Y182    8:0:0:192     #############################
# Tile (HCLK_R_BOT_UTURN) HCLK_R_BOT_UTURN_X106Y182    8:0:0:96     #############################
# Tile (HCLK_TERM) HCLK_TERM_X2Y182    0:0:0:0
# Tile (HCLK_TERM_GTX) HCLK_TERM_GTX_X129Y182    0:0:0:0
# Tile (HCLK_VBRK) HCLK_VBRK_X9Y182    0:0:0:0
# Tile (HCLK_VFRAME) HCLK_VFRAME_X47Y182    0:0:0:0
# Tile (INT_FEEDTHRU_1) INT_FEEDTHRU_1_X35Y155    0:0:0:0
# Tile (INT_FEEDTHRU_2) INT_FEEDTHRU_2_X36Y155    0:0:0:0
# Tile (INT_INTERFACE_L) INT_INTERFACE_L_X18Y199    24:0:0:0
# Tile (INT_INTERFACE_R) INT_INTERFACE_R_X1Y199    24:0:0:0
# Tile (INT_L) INT_L_X0Y199    44:64:0:3629     #############################
# Tile (INT_R) INT_R_X1Y199    42:64:0:3631     #############################
# Tile (IO_INT_INTERFACE_L) IO_INT_INTERFACE_L_X0Y199    24:0:0:0
# Tile (IO_INT_INTERFACE_R) IO_INT_INTERFACE_R_X57Y149    24:0:0:0
# Tile (LIOB33) LIOB33_X0Y197    10:0:0:0
# Tile (LIOB33_SING) LIOB33_SING_X0Y199    0:0:0:0
# Tile (LIOI3) LIOI3_X0Y197    167:0:12:242     #############################
# Tile (LIOI3_SING) LIOI3_SING_X0Y199    72:0:6:121     #############################
# Tile (LIOI3_TBYTESRC) LIOI3_TBYTESRC_X0Y193    162:0:12:242     #############################
# Tile (LIOI3_TBYTETERM) LIOI3_TBYTETERM_X0Y187    160:0:12:242     #############################
# Tile (L_TERM_INT) L_TERM_INT_X2Y207    0:0:0:0
# Tile (MONITOR_BOT) MONITOR_BOT_X46Y131    117:0:0:0
# Tile (MONITOR_MID) MONITOR_MID_X46Y141    12:0:0:0
# Tile (MONITOR_TOP) MONITOR_TOP_X46Y151    8:0:0:0
# Tile (NULL) NULL_X0Y208    0:0:0:0
# Tile (PCIE_BOT) PCIE_BOT_X104Y167    1736:0:0:0
# Tile (PCIE_INT_INTERFACE_L) PCIE_INT_INTERFACE_L_X44Y174    72:0:0:96     #############################
# Tile (PCIE_INT_INTERFACE_R) PCIE_INT_INTERFACE_R_X41Y174    72:0:0:96     #############################
# Tile (PCIE_NULL) PCIE_NULL_X104Y181    0:0:0:0
# Tile (PCIE_TOP) PCIE_TOP_X104Y177    441:0:0:0
# Tile (RIOB33) RIOB33_X57Y147    9:0:0:0
# Tile (RIOB33_SING) RIOB33_SING_X57Y149    0:0:0:0
# Tile (RIOI3) RIOI3_X57Y147    167:0:12:242     #############################
# Tile (RIOI3_SING) RIOI3_SING_X57Y149    72:0:6:121     #############################
# Tile (RIOI3_TBYTESRC) RIOI3_TBYTESRC_X57Y143    162:0:12:242     #############################
# Tile (RIOI3_TBYTETERM) RIOI3_TBYTETERM_X57Y137    160:0:12:242     #############################
# Tile (R_TERM_INT) R_TERM_INT_X145Y155    0:0:0:0
# Tile (R_TERM_INT_GTX) R_TERM_INT_GTX_X128Y207    0:0:0:0
# Tile (TERM_CMT) TERM_CMT_X8Y208    0:0:0:0
# Tile (T_TERM_INT) T_TERM_INT_X4Y208    0:0:0:0
# Tile (VBRK) VBRK_X9Y207    0:0:0:0
# Tile (VBRK_EXT) VBRK_EXT_X129Y207    0:0:0:0
# Tile (VFRAME) VFRAME_X47Y207    0:0:0:0

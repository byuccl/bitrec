
proc srch { f p depth maxdepth} {
    for {set i 0} {$i < $depth} {incr i} {
        puts -nonewline $f "   "
        puts -nonewline  "   "
    }

    puts -nonewline $f "$depth $p"
    puts -nonewline "$depth $p"
    set n [get_nodes -uphill -of $p]
    set spin [get_site_pin -quiet -of $n]
    if { $spin == "" } {
        puts $f " nopin"
        puts " nopin"
    } else {
        puts $f "  <<$spin>>"
        puts "  <<$spin>>"
    }

    if { $depth == $maxdepth } {
        return
    }

    set dpips [get_pips -quiet -uphill -of $p]
    foreach dpip $dpips {
        srch $f $dpip [expr {$depth + 1}] $maxdepth
    }


    if {$depth < $maxdepth } {
    }

}

# To open chip:   link_design -part xc7a100ticsg324-1L
link_design -part xc7a100ticsg324-1L
#set p [get_pips INT_L_X6Y10/INT_L.FAN_ALT7->>FAN_BOUNCE7]
set p [get_pips INT_L_X6Y10/INT_L.GCLK_L_B10_WEST->>GFAN0]
set p [get_pips INT_L_X50Y156/INT_L.NR1END2->>CTRL_L1]
set p [get_pips INT_L_X6Y10/INT_L.GCLK_L_B10_WEST->>GFAN0]
set f [open /tmp/log.txt w]

srch $f $p 0 4

#close $f

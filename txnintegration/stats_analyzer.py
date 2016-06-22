import csv
import argparse
import sys
import os.path

mpl_imported = True
try:
    import matplotlib.pyplot as plt
except ImportError:
    print "matplotlib not available on this platform - plotting disabled"
    print "see http://matplotlib.org/users/installing.html"
    mpl_imported = False


def display_headings(infile):
    f = open(infile, 'rb')
    csv_reader = csv.reader(f)
    row = next(csv_reader)

    table = []
    maxcolumnwidth = []

    headings = len(row)

    table_columns = 4
    table_rows = len(row) / table_columns

    if (table_columns * table_rows) < headings:
        table_rows += 1

    index = 0
    for table_column in range(0, table_columns):
        table_column = []
        width = []
        for _ in range(0, table_rows):
            dn = "({0}) {1}".format(index, row[index])
            table_column.append(dn)
            width.append(len(dn))
            index += 1
            if index == headings:
                break
        table.append(table_column)
        maxcolumnwidth.append(max(width))

    print "available fields in stats file:"
    heading_index = 0
    for rownum in range(0, table_rows):
        column_index = 0
        for column in table:
            print "{0:{1}}".format(column[rownum],
                                   maxcolumnwidth[column_index]),
            column_index += 1
            heading_index += 1
            if heading_index == headings:
                break
        print


field_index = {}
field_data = {}
time_data = []


def read_data(infile, headings):
    with open(infile, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        firstrow = True
        secondrow = True
        thirdrow = True

        for row in reader:
            if firstrow:
                index = 0
                for heading in headings:
                    field_index[heading] = row.index(heading)
                    field_data[heading] = []
                    index += 1
                firstrow = False
            elif secondrow:
                # throw away the second row
                secondrow = False
            else:
                if thirdrow:
                    # make the first timestamp = 0
                    timeoffset = float(row[0])
                    thirdrow = False
                time_data.append(float(row[0]) - timeoffset)

                for heading in headings:
                    index = field_index[heading]
                    field_data[heading].append(float(row[index]))
                firstrow = False


def plot_all(headings):
    # utility - plot all data series
    fig = plt.figure()
    plotcount = len(headings)
    plotnum = 1
    for heading in headings:
        h1 = heading
        ax1 = fig.add_subplot(plotcount, 1, plotnum)
        ax1.set_title(h1, fontsize=10)
        ax1.plot(time_data, field_data[h1], 'b-')
        ymax = max(field_data[h1])
        ymin = min(field_data[h1])
        ax1.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
        if plotnum != plotcount:
            ax1.xaxis.set_visible(False)
        ax1.tick_params(axis='both', which='major', labelsize=10)
        ax1.tick_params(axis='both', which='minor', labelsize=8)
        plotnum += 1

    fig.subplots_adjust(hspace=.25)

    plt.show()

    fig = plt.figure()


def do_summary_plot(infile):
    headings = [
        'sys_blocks_blocks_max_committed',
        'sys_blocks_blocks_max_committed_count',
        'sys_blocks_blocks_min_committed',
        'sys_blocks_blocks_max_pending',
        'sys_txns_txns_max_committed',
        'sys_txns_txns_max_committed_count',
        'sys_txns_txns_max_pending',
        'sys_txns_txns_max_pending_count',
        'sys_txns_txns_min_pending',
        'scpu_percent'
    ]
    read_data(infile, headings)
    plot_summary(infile)


def plot_summary(infile):
    # plot summary results
    fig = plt.figure()

    h1 = "sys_blocks_blocks_max_committed"
    h2 = "sys_blocks_blocks_min_committed"
    ax1 = fig.add_subplot(5, 1, 1)
    ax1.set_title(h1, fontsize=10)
    ax1.plot(time_data, field_data[h1], 'b-')
    ax1.plot(time_data, field_data[h2], 'r:')
    ymax = max(field_data[h1])
    ymin = min(field_data[h1])
    ax1.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
    ax1.tick_params(axis='both', which='major', labelsize=10)
    ax1.tick_params(axis='both', which='minor', labelsize=8)
    ax1.xaxis.set_visible(False)

    countonaxis = False
    if countonaxis:
        ax12 = ax1.twinx()
        h2 = "sys_blocks_blocks_max_committed_count"
        ax12.plot(time_data, field_data[h2], 'g-')
        ax12.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
        ax12.xaxis.set_visible(False)

    h1 = "sys_blocks_blocks_max_committed_count"
    ax2 = fig.add_subplot(5, 1, 2)
    ax2.set_title(h1, fontsize=10)
    ax2.plot(time_data, field_data[h1], 'b-')
    ymax = max(field_data[h1])
    ymin = min(field_data[h1])
    ax2.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
    ax2.tick_params(axis='both', which='major', labelsize=10)
    ax2.tick_params(axis='both', which='minor', labelsize=8)
    ax2.xaxis.set_visible(False)

    h1 = "sys_txns_txns_max_pending"
    h2 = "sys_txns_txns_min_pending"
    ax3 = fig.add_subplot(5, 1, 3)
    ax3.set_title(h1, fontsize=10)
    ax3.plot(time_data, field_data[h1], 'b-')
    ax3.plot(time_data, field_data[h2], 'r:')
    ymax = max(field_data[h1])
    ymin = min(field_data[h1])
    ax3.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
    ax3.tick_params(axis='both', which='major', labelsize=10)
    ax3.tick_params(axis='both', which='minor', labelsize=8)
    ax3.xaxis.set_visible(False)

    h1 = "sys_txns_txns_max_pending_count"
    ax4 = fig.add_subplot(5, 1, 4)
    ax4.set_title(h1, fontsize=10)
    ax4.plot(time_data, field_data[h1], 'b-')
    ymax = max(field_data[h1])
    ymin = min(field_data[h1])
    ax4.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
    ax4.tick_params(axis='both', which='major', labelsize=10)
    ax4.tick_params(axis='both', which='minor', labelsize=8)
    ax4.xaxis.set_visible(False)

    h1 = "scpu_percent"
    ax4 = fig.add_subplot(5, 1, 5)
    ax4.set_title(h1, fontsize=10)
    ax4.plot(time_data, field_data[h1], 'b-')
    ymax = max(field_data[h1])
    ymin = min(field_data[h1])
    ax4.set_ylim([ymin, ymin + 1.2 * (ymax - ymin)])
    ax4.tick_params(axis='both', which='major', labelsize=10)
    ax4.tick_params(axis='both', which='minor', labelsize=8)

    fig.suptitle(infile)

    fig.subplots_adjust(hspace=.25)

    plt.show()


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--statsfile',
                        metavar="",
                        help='Base validator url (default: %(default)s)',
                        default="")

    return parser.parse_args(args)


def configure(opts):
    pass


def main():
    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    configure(opts)

    fname = 'stats_client_1466786949.csv'

    infile = ""
    if opts.statsfile != "":
        fname = opts.statsfile
        if os.path.isfile(fname):
            infile = fname
        else:
            print "file not found: ", fname
            print "ensure file is in same directory as stats analyzer"
            sys.exit()
    elif fname != "":
        if os.path.isfile(fname):
            infile = fname
        else:
            print "no csv file found:"
            print "- generate stats csv file by running stats client with "
            print "--csv-enable = True option"
            sys.exit()
    else:
        print "no filename specified "
        print "- generate stats csv file by running stats client with "
        print "--csv-enable = True option"
        sys.exit()

    print "stats file to analyze: ", infile

    display_headings(infile)

    if mpl_imported:
        do_summary_plot(infile)


if __name__ == "__main__":
    main()

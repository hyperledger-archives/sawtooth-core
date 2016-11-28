function package_group_install() {
    group=$1
    dist_name=$(lsb_release -i -s | tr '[A-Z]' '[a-z]')
    dist_version=$(lsb_release -r -s)

    filename=/vagrant/package_groups/$dist_name-$dist_version-$group

    if [ -f $filename ]; then
        pkgs=$(cat $filename \
            | sed -e "s/@KERNEL_RELEASE@/$(uname -r)/")
        if [ "$dist_name" = "ubuntu" ]; then
            apt-get install -y $pkgs || return 1
        else
            echo "Unsupported distribution: $dist_name" 1>&2
            return 1
        fi
    else
        echo "No such package group file: $filename" 1>&2
        return 1
    fi

    return 0
}

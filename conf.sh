
if [[ -e conf-local.sh ]]; then
    . conf-local.sh
elif [[ -e /vagrant/conf-local.sh ]]; then
    . /vagrant/conf-local.sh
fi

if [[ -e conf-defaults.sh ]]; then
    . conf-defaults.sh
else
    . /vagrant/conf-defaults.sh
fi


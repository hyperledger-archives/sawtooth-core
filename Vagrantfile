# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  if ARGV.include? "up"
    repo_error = false
    ["../sawtooth-core", "../sawtooth-validator", "../sawtooth-mktplace"].each do |repo|
      if !File.directory?(repo)
        STDERR.puts("Repository " + repo + " needs to exist")
        repo_error = true
      end
    end
    if repo_error
      exit
    end

    if Vagrant.has_plugin?("vagrant-proxyconf")
        puts "Configuring proxyconf plugin!"
        if ENV["http_proxy"]
            puts "http_proxy: " + ENV["http_proxy"]
            config.proxy.http     = ENV["http_proxy"]
        end
        if ENV["https_proxy"]
            puts "https_proxy: " + ENV["https_proxy"]
            config.proxy.https    = ENV["https_proxy"]
        end
        if ENV["no_proxy"]
            puts "no_proxy: " + ENV["no_proxy"]
            config.proxy.no_proxy = ENV["no_proxy"]
        end
    else
        puts "Proxyconf plugin not found"
        puts "Install: vagrant plugin install vagrant-proxyconf"
    end
  end

  config.vm.provider "virtualbox" do |v|
    v.memory = 2048
    v.cpus = 2
  end

  config.vm.box = "ubuntu/trusty64"
  #config.vm.box = "bento/opensuse-13.2"

  config.vm.network "forwarded_port", guest: 8800, host: 8800
  config.vm.network "forwarded_port", guest: 8900, host: 8900

  # rethinkdb
  config.vm.network "forwarded_port", guest: 18080, host: 18080

  config.vm.provision :shell, path: "bootstrap.sh"

  config.vm.synced_folder "../", "/project"
end
